from hashlib import sha256
from typing import Any, Dict, List, Optional, Set, Tuple, cast
import renderdoc as rd
from yk_analysis.analysis_helpers.db import ReadOnlyDb

ShaderNameSet = Optional[Set[Tuple[str, str]]]

def condensed_manyname(names: ShaderNameSet) -> str:
    if not names:
        return "??"
    elif len(names) == 1:
        cat, shader = next(iter(names))
        return shader
    else:
        return "(" + " | ".join(shader for _cat, shader in names) + ")"

def perform_analysis(r: rd.ReplayController, db_path: str, dbg_file) -> Tuple[Dict[rd.ResourceId, ShaderNameSet], Dict[int, str]]:
    if dbg_file:
        cnt = 0
        def print_d(*args):
            nonlocal cnt
            cnt += 1
            dbg_file.write(f"dbg {cnt}: {' '.join(str(a) for a in args)}\n")
            dbg_file.flush()
            # mqt.InvokeOntoUIThread(lambda: ctx.Extensions().MessageDialog(f"dbg {cnt}: {s}", "Extension message"))
    else:
        def print_d(*args):
            pass

    print_d("opening db")
    db = ReadOnlyDb(db_path, expected_version=1)
    print_d("opened db")      
    
    shader_names: Dict[rd.ResourceId, ShaderNameSet] = {}

    # Given a RenderDoc shader object, translates its data into DB-compatible formats and looks it up in the DB.
    # If this shader has been lookedup before, returns the contents of shader_names[s.resourceId].
    # Otherwise sets shader_names[s.resourceId] with the possible names retrieved from the DB.
    def lookup_shader_in_db(s: rd.D3D11Shader) -> ShaderNameSet:
        if s.resourceId in shader_names:
            return shader_names[s.resourceId]
        shader_names[s.resourceId] = None
        print_d("resourceId", s.resourceId)

        print_d("stage", s.stage)
        if s.stage == rd.ShaderStage.Vertex:
            shader_stage = "Vertex"
        elif s.stage == rd.ShaderStage.Pixel:
            shader_stage = "Fragment"
        else:
            return None
        
        print_d("encoding", s.reflection.encoding)
        if s.reflection.encoding == rd.ShaderEncoding.DXBC:
            bytes_type = "DXBC"
        else:
            return None
        
        h = sha256()
        h.update(s.reflection.rawBytes)
        d = h.digest()
        print_d("digest", d)
        
        db.cur.execute("SELECT Category, ShaderName FROM ShaderBytes WHERE ShaderStage = ? AND BytesType = ? AND SHA256 = ?", (shader_stage, bytes_type, d, ))
        possible_names: Optional[Set[Tuple[str, str]]] = set(
            (str(cat), str(s_name))
            for cat, s_name in db.cur.fetchall()
        )
        if not possible_names:
            possible_names = None
        print_d(f"shaderId@", s.resourceId, shader_stage, bytes_type, possible_names)
        shader_names[s.resourceId] = possible_names
        return possible_names
    
    # Given a pair of shaders, looks up both of them in the DB, sees if they have a common name and if so sets both their entries in shader_names to just that name.
    def lookup_shader_pair(vert: rd.D3D11Shader, pix: rd.D3D11Shader) -> Tuple[ShaderNameSet, ShaderNameSet]:
        vert_names = lookup_shader_in_db(vert)
        pix_names = lookup_shader_in_db(pix)

        if vert_names is None or pix_names is None:
            return vert_names, pix_names

        common_names = vert_names.intersection(pix_names)
        if common_names:
            print_d("intersected vertId@", vert.resourceId, "pixId@", pix.resourceId, "new names", common_names)
            # These are references to the objects inside shader_names
            vert_names.intersection_update(common_names)
            # shader_names[pix.resourceId] = vert_names # Don't do intersection_update, make them literally the same object so further refinements apply to both
            pix_names.intersection_update(common_names)
        return vert_names, pix_names

    action_names: Dict[int, str] = {}

    # First pass: find correct shader_names
    # Start iterating from the first real action as a child of markers
    action = cast(rd.ActionDescription, r.GetRootActions()[0])
    while len(action.children) > 0:
        action = action.children[0]

    while action is not None:
        if action.flags & rd.ActionFlags.Drawcall:
            r.SetFrameEvent(action.eventId, False) # force=False
            d3d11state = r.GetD3D11PipelineState()
            vertex_name, pixel_name = lookup_shader_pair(d3d11state.vertexShader, d3d11state.pixelShader)

            print_d("action@", action.eventId, "vertId@",  d3d11state.vertexShader.resourceId, vertex_name, "pixId@", d3d11state.pixelShader.resourceId,  pixel_name)

        action = action.next

    # Second pass: find new action names
    # Start iterating from the first real action as a child of markers
    action = cast(rd.ActionDescription, r.GetRootActions()[0])
    while len(action.children) > 0:
        action = action.children[0]

    while action is not None:
        if action.flags & rd.ActionFlags.Drawcall:
            r.SetFrameEvent(action.eventId, False) # force=False
            d3d11state = r.GetD3D11PipelineState()
            
            vertex_name = shader_names.get(d3d11state.vertexShader.resourceId)
            pixel_name = shader_names.get(d3d11state.pixelShader.resourceId)
            if vertex_name is None and pixel_name is None:
                action_name = None
            elif vertex_name == pixel_name:
                action_name = f"{condensed_manyname(vertex_name)}"
            else:
                action_name = f"{condensed_manyname(vertex_name)} - {condensed_manyname(pixel_name)}"
            
            if action_name:
                # action.GetName returns some extra cruft e.g. "ID3D11DeviceContext::DrawIndexed()" instead of DrawIndexed
                if action.indexOffset:
                    old_name = f"DrawIndexed({action.numIndices})"
                else:
                    old_name = f"Draw({action.numIndices})"
                # old_name = action.GetName(r.GetStructuredFile())
                action_names[action.eventId] = f"{old_name} - {action_name}"

        action = action.next

    return shader_names, action_names
import functools
from hashlib import sha256
from typing import Any, Dict, List, Optional, Set, Tuple, cast
import renderdoc as rd
import qrenderdoc as qrd
import PySide2.QtWidgets as widgets

from yk_analysis.analysis_helpers.db import ReadOnlyDb

Widget = Any

# class YakuzaScanWindow(qrd.CaptureViewer):
#     mqt: qrd.MiniQtHelper
#     ctx: qrd.CaptureContext
#     top_window: Widget

#     def __init__(self, ctx: qrd.CaptureContext, version: str):
#         super().__init__()

#         self.mqt = ctx.Extensions().GetMiniQtHelper()

#         self.ctx = ctx
#         self.version = version
#         self.top_window = self.mqt.CreateToplevelWidget("Yakuza Scanner", lambda c, w, d: on_window_closed())

#         vert = self.mqt.CreateVerticalContainer()
        
#         widgets.QFileDialog

#         self.mqt.AddWidget(self.top_window, vert)

#     def OnCaptureLoaded(self):
#         pass

#     def OnCaptureClosed(self):
#         pass

#     def OnSelectedEventChanged(self, event):
#         pass

#     def OnEventChanged(self, event):
#         pass

extiface_version = ''
# cur_window: Optional[YakuzaScanWindow] = None

def register(version: str, ctx: qrd.CaptureContext):
    global extiface_version
    extiface_version = version

    print("Registering my extension for RenderDoc version {}".format(version))

    # ctx.Extensions().RegisterWindowMenu(qrd.WindowMenu.Window, ["Extension Window"], open_window_callback)
    ctx.Extensions().RegisterWindowMenu(qrd.WindowMenu.Tools, ["Yakuza Scan"], menu_callback)
    ctx.Extensions().RegisterWindowMenu(qrd.WindowMenu.Tools, ["Yakuza Scan (Debug)"], menu_callback_dbg)

def unregister():
    print("Unregistering my extension")

    # Force close the window, if it's open
    # global cur_window
    # if cur_window is not None:
    #     cur_window.mqt.CloseToplevelWidget(cur_window.top_window)
    # cur_window = None
    pass

def open_window_callback(ctx: qrd.CaptureContext, data):
    # global cur_window
    # if cur_window is None:
    #     cur_window = YakuzaScanWindow(ctx, extiface_version)
    #     if ctx.HasEventBrowser():
    #         ctx.AddDockWindow(cur_window.top_window, qrd.DockReference.TopOf, ctx.GetEventBrowser().Widget(), 0.1)
    #     else:
    #         ctx.AddDockWindow(cur_window.top_window, qrd.DockReference.MainToolArea, None)
    #     ctx.AddCaptureViewer(cur_window)
    # ctx.RaiseDockWindow(cur_window.top_window)
    pass

def on_window_closed():
    # global cur_window
    # if cur_window is not None:
    #     cur_window.ctx.RemoveCaptureViewer(cur_window)
    # cur_window = None
    pass

# Plugin structure:
# - On clicking a button, open a window
# - The window has file pickers for a shader database and a model database
# - and a button for starting analysis
# When you start analysis
# - jump onto the replay thread
# - open a connection to the databases
# - create a view of (ShaderName, NumIndices[all setups], GMDFile, NodeName, DrawOrder)
# - use the ReplayController, go to the start of the frame, iterate through all actions
    # - if it's a draw action (action.flags & ActionFlags.Drawcall?), SetFrameEvent() on the last event in GetRootActions(), then GetD3D11PipelineState()
    # - d3d11state.vertexShader.resourceID Lookup that resource ID in a local map to see if you've already analysed it. If you haven't, hash d3d11state.vertexShader.reflection.rawBytes (assert .encoding == ShaderEncoding.DXBC), look it up in the shader DB and find the shader name.
    # -     SetResourseCustomName(d3d11state.vertexShader.resourceID, <full shader name>)
    # - check d3d11state.pixelShader is consistent
    # - lookup the (shadername[:30], action.numIndices) against a column (use d3d11state.inputAssembly.topology == Topology.TriangleList/Strip) and assign action.customName = f"{shader}.{gmdfile}.{nodename}.{draworder}" if there's only one distinct answer

def menu_callback(ctx: qrd.CaptureContext, data):
    db_path, _selected_filter = widgets.QFileDialog.getOpenFileName(caption="Select Yakuza Game Shader DB Path")
    if not db_path:
        ctx.Extensions().MessageDialog("No database selected!", "Extension message")
        return
    
    mqt = ctx.Extensions().GetMiniQtHelper()

    ctx.Replay().AsyncInvoke('', lambda r: perform_analysis(ctx, r, mqt, db_path, debug=False))

def menu_callback_dbg(ctx: qrd.CaptureContext, data):
    db_path, _selected_filter = widgets.QFileDialog.getOpenFileName(caption="Select Yakuza Game Shader DB Path")
    if not db_path:
        ctx.Extensions().MessageDialog("No database selected!", "Extension message")
        return
    
    mqt = ctx.Extensions().GetMiniQtHelper()

    ctx.Replay().AsyncInvoke('', lambda r: perform_analysis(ctx, r, mqt, db_path, debug=True))

def perform_analysis(ctx: qrd.CaptureContext, r: rd.ReplayController, mqt: qrd.MiniQtHelper, db_path: str, debug: bool):
    try:
        perform_analysis_inner(ctx, r, mqt, db_path, debug=debug)
        err_msg = None
    except Exception as err:
        err_msg = f"{err}"
    finally:
        if err_msg:
            mqt.InvokeOntoUIThread(lambda: ctx.Extensions().ErrorDialog(f"{err_msg}", "Extension message"))

def perform_analysis_inner(ctx: qrd.CaptureContext, r: rd.ReplayController, mqt: qrd.MiniQtHelper, db_path: str, debug: bool = False):
    if debug:
        cnt = 0
        # TODO don't use hardcoded path
        dbg_file = open("C:\\Users\\Samuel\\ext_dbg_temp.txt", "a")
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
    
    shader_names: Dict[rd.ResourceId, Optional[Set[Tuple[str, str]]]] = {}

    # Given a RenderDoc shader object, translates its data into DB-compatible formats and looks it up in the DB.
    # If this shader has been lookedup before, returns the contents of shader_names[s.resourceId].
    # Otherwise sets shader_names[s.resourceId] with the possible names retrieved from the DB.
    def lookup_shader_in_db(s: rd.D3D11Shader) -> Optional[Set[Tuple[str, str]]]:
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
    def lookup_shader_pair(vert: rd.D3D11Shader, pix: rd.D3D11Shader) -> Tuple[Optional[Set[Tuple[str, str]]], Optional[Set[Tuple[str, str]]]]:
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

    def condensed_manyname(names: Optional[Set[Tuple[str, str]]]) -> str:
        if not names:
            return "??"
        elif len(names) == 1:
            cat, shader = next(iter(names))
            return shader
        else:
            return "(" + " | ".join(shader for _cat, shader in names) + ")"

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

    if debug:
        dbg_file.close()

    # Final pass - in the UI thread, actually update the names
    def finish():
        for resourceId, possible_names in shader_names.items():
            if not possible_names:
                continue
            ctx.SetResourceCustomName(resourceId, condensed_manyname(possible_names))
        for eventId, action_name in action_names.items():
            # ctx.SetFrameEvent(eventId) # Update the name in the UI
            ctx.GetAction(eventId).customName = action_name
        ctx.Extensions().MessageDialog(f"Done!", "Extension message")

    mqt.InvokeOntoUIThread(finish)


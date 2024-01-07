import functools
from hashlib import sha256
from typing import Any, Dict, List, Optional, Set, cast
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

    def lookup_shader_bytes_in_db(shader_stage: str, bytes_type: str, b: bytes) -> Optional[str]:
        h = sha256()
        h.update(b)
        d = h.digest()
        print_d("digest", d)
        
        db.cur.execute("SELECT Category, ShaderName FROM ShaderBytes WHERE ShaderStage = ? AND BytesType = ? AND SHA256 = ?", (shader_stage, bytes_type, d, ))
        data = set(
            (str(cat), str(s_name))
            for cat, s_name in db.cur.fetchall()
        )
        print_d("recalled shaders", data)
        if len(data) == 1:
            cat, s_name = next(iter(data))
            return s_name
        return None
    
    shader_names: Dict[rd.ResourceId, Optional[str]] = {}

    def lookup_shader_in_db(s: rd.D3D11Shader) -> Optional[str]:
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
        
        name = lookup_shader_bytes_in_db(shader_stage, bytes_type, s.reflection.rawBytes)
        if name is None:
            return None
        # print_d(name)
        shader_names[s.resourceId] = name

        print_d(f"@{s.resourceId} {shader_stage} {bytes_type} {s.reflection.rawBytes[:16]} {name}")
        
        # Don't call this from the replay thread - things break
        # ctx.SetResourceCustomName(s.resourceId, f"{name} ({shader_stage})")
        return name

    # Start iterating from the first real action as a child of markers
    action = cast(rd.ActionDescription, r.GetRootActions()[0])
    while len(action.children) > 0:
        action = action.children[0]

    print_d(action)

    while action is not None:
        print_d(f"{action}, {action.flags}")

        if action.flags & rd.ActionFlags.Drawcall:
            r.SetFrameEvent(action.eventId, False) # force=False
            print_d("set frame event")
            d3d11state = r.GetD3D11PipelineState()
            print_d(d3d11state.vertexShader)
            vertex_name = lookup_shader_in_db(d3d11state.vertexShader)
            fragment_name = lookup_shader_in_db(d3d11state.pixelShader)
            print_d("names", vertex_name, fragment_name)
            if vertex_name is None and fragment_name is None:
                # Don't set a custom name
                custom_name = None
            elif vertex_name == fragment_name:
                custom_name = f"{vertex_name}"
            else:
                custom_name = f"{vertex_name} - {fragment_name}"

            if custom_name is not None:
                print_d(f"Setting custom name '{custom_name}'")
                # TODO maybe don't do this from here - the UI thread doesn't uncache them
                action.customName = custom_name

        action = action.next

    if debug:
        dbg_file.close()

    def finish():
        for resourceId, name in shader_names.items():
            if not name:
                continue
            ctx.SetResourceCustomName(resourceId, f"{name}")
        ctx.Extensions().MessageDialog(f"Done!", "Extension message")

    mqt.InvokeOntoUIThread(finish)


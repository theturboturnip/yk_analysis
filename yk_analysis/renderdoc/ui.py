import renderdoc as rd
import qrenderdoc as qrd
import PySide2.QtWidgets as widgets
from yk_analysis.renderdoc.analyse import condensed_manyname, perform_analysis

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

    ctx.Replay().AsyncInvoke('', lambda r: analysis_ui_wrapper(ctx, r, mqt, db_path, debug=False))

def menu_callback_dbg(ctx: qrd.CaptureContext, data):
    db_path, _selected_filter = widgets.QFileDialog.getOpenFileName(caption="Select Yakuza Game Shader DB Path")
    if not db_path:
        ctx.Extensions().MessageDialog("No database selected!", "Extension message")
        return
    
    mqt = ctx.Extensions().GetMiniQtHelper()

    ctx.Replay().AsyncInvoke('', lambda r: analysis_ui_wrapper(ctx, r, mqt, db_path, debug=True))

def analysis_ui_wrapper(ctx: qrd.CaptureContext, r: rd.ReplayController, mqt: qrd.MiniQtHelper, db_path: str, debug: bool):
    try:
        if debug:
            # TODO hardcoded path
            dbg_file = open("C:\\Users\\Samuel\\ext_dbg.temp.txt", "a")
        else:
            dbg_file = None

        shader_names, action_names = perform_analysis(r, db_path, dbg_file)
        def finish():
            for resourceId, possible_names in shader_names.items():
                if not possible_names:
                    continue
                ctx.SetResourceCustomName(resourceId, condensed_manyname(possible_names))
            for eventId, action_name in action_names.items():
                # ctx.SetFrameEvent(eventId) # Update the name in the UI
                ctx.GetAction(eventId).customName = action_name
            ctx.Extensions().MessageDialog(f"Done!")
        mqt.InvokeOntoUIThread(finish)

        err_msg = None
    except Exception as err:
        err_msg = f"{err}"
    finally:
        if dbg_file:
            dbg_file.close()
        if err_msg:
            mqt.InvokeOntoUIThread(lambda: ctx.Extensions().ErrorDialog(f"{err_msg}"))
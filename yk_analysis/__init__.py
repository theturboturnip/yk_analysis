try:
    import renderdoc as rd
    import qrenderdoc as qrd

    renderdoc_present = True
except ImportError:
    renderdoc_present = False
    pass

# try:
#     pyrenderdoc
#     renderdoc_ui_present = True
# except NameError:
#     renderdoc_ui_present = False

if renderdoc_present: # and renderdoc_ui_present:
    # TODO don't try to import renderdoc.ui if we're running in a shell script? 'pyrenderdoc' in globals() doesn't work as a test for this though...
    from .renderdoc.ui import *
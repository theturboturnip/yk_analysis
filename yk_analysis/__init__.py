try:
    import renderdoc as rd
    import qrenderdoc as qrd

    renderdoc_present = True
except ImportError:
    renderdoc_present = False
    pass

if renderdoc_present:
    from .renderdoc import *
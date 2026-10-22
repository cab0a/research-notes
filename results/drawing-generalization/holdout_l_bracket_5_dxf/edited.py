# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'base_thickness': 6.6, 'height': 38.0, 'length': 35.0, 'wall_thickness': 5.0, 'width': 71.0}
OPENING='top'
SOURCE_SHA256='44306fe6c7c94dfc79e87c231b283211bec663ae73d4dcd9f1f6af3e9035953b'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])

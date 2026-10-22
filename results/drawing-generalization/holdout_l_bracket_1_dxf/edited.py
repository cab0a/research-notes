# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'base_thickness': 5.0, 'height': 38.0, 'length': 42.0, 'wall_thickness': 3.0, 'width': 66.0}
OPENING='top'
SOURCE_SHA256='3e35d3262345b7127914e6d1c5f20e50d032bd13b7a5c91a49cfc4a02ac87956'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])

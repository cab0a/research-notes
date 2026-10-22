# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='l_bracket'
PARAMETERS={'width': 58.0, 'length': 49.0, 'height': 37.0, 'wall_thickness': 3.5, 'base_thickness': 4.4}
OPENING='top'
SOURCE_SHA256='ae2dba631b796fed41eb42fcfddbaf9a21f19b18c159a91e34f95c6133f0a004'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])

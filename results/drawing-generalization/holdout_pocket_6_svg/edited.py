# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='pocket'
PARAMETERS={'length': 55.0, 'pocket_depth': 7.5, 'pocket_length': 17.0, 'pocket_width': 25.0, 'pocket_x': 12.5, 'pocket_y': 10.5, 'thickness': 19.0, 'width': 92.0}
OPENING='bottom'
SOURCE_SHA256='5f0e16766421643f87ac1f999c3cc083fb0172651cda8359395b9e0fdbfdecdf'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])

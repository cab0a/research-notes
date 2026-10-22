# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'holes': [{'diameter': 7.5, 'x': 21.24, 'y': 12.48}], 'length': 48.0, 'thickness': 14.0, 'width': 93.0}
OPENING='top'
SOURCE_SHA256='d7bd82db8eda14ebbeae2a53eb0f6cf6d4b05be5902bee58768ccc9ddd0c61c9'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])

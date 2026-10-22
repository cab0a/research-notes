# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'width': 54.0, 'length': 40.0, 'thickness': 8.0, 'holes': [{'x': 12.0, 'y': 10.0, 'diameter': 6.0}, {'x': 38.0, 'y': 28.0, 'diameter': 8.0}]}
SOURCE_SHA256 = '061fa761c93ac989b9677f08ec4c808d3ed3123f29442933318e72d81d8eb0b2'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])

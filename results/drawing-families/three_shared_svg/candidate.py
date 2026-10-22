# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'plate'
PARAMETERS = {'width': 54.0, 'length': 40.0, 'thickness': 8.0, 'holes': [{'x': 12.0, 'y': 10.0, 'diameter': 6.0}, {'x': 12.0, 'y': 28.0, 'diameter': 6.0}, {'x': 38.0, 'y': 20.0, 'diameter': 6.0}]}
SOURCE_SHA256 = '4600c34adcff07721b86a822493e99be0f4ab61717c668690f488180422333b8'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])

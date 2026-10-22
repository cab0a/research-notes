# Editable generated recipe; not recovered original feature history.
from research_notes.drawing_families import export_family
FAMILY = 'stepped_shaft'
PARAMETERS = {'length1': 24.0, 'length2': 16.0, 'diameter1': 16.0, 'diameter2': 10.0}
SOURCE_SHA256 = 'b71f3f86b5223208cc5429ca575b66acdde11cd567ddecb45e4c415261df2782'
if __name__ == '__main__':
    import sys
    export_family(FAMILY, PARAMETERS, sys.argv[1])

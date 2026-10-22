# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'width': 40.0, 'length': 30.0, 'thickness': 8.0, 'holes': [{'x': 28.0, 'y': 21.0, 'diameter': 6.0}, {'x': 10.0, 'y': 8.0, 'diameter': 4.0}]}
SOURCE_SHA256 = '6b23e74ea3e4e1af05a82ef4803593fbd52901dc4ccf2ba311aa7500f277e25b'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)

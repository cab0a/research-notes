# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'width': 40.0, 'length': 30.0, 'thickness': 8.0, 'holes': [{'x': 12.0, 'y': 10.0, 'diameter': 6.0}]}
SOURCE_SHA256 = '8d0c86451962a031aa31231216d77cb70a644a7a9ab02f33dee4774ab974b35e'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)

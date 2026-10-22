# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'width': 40.0, 'length': 30.0, 'thickness': 8.0, 'holes': [{'x': 12.0, 'y': 10.0, 'diameter': 6.0}]}
SOURCE_SHA256 = '653754b134a355fd430b59d92c0821c560147449b1d87425c365bb5316357bbb'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)

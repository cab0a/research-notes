# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'holes': [{'diameter': 6.5, 'x': 18.5, 'y': 13.25}], 'length': 37.25, 'thickness': 8.5, 'width': 57.5}
SOURCE_SHA256 = 'fa520f613aa4afb5e5834129fb95c44e3bba4b13ab7bdc81ef3535824565dcb3'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)

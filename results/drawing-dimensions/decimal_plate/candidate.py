# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'width': 52.5, 'length': 37.25, 'thickness': 6.5, 'holes': [{'x': 17.5, 'y': 13.25, 'diameter': 5.5}]}
SOURCE_SHA256 = 'ba0b62aca2d7d4dada9a9c14bf3ed755db912b1fe31c6f7c5ca966125dd1b47f'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)

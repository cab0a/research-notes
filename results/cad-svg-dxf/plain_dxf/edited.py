# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'holes': [], 'length': 30.0, 'thickness': 10.0, 'width': 45.0}
SOURCE_SHA256 = '6d37650d3b7a90e5af2e4f748fc83030736e959c0af78f1d7efcaa09581ac2df'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)

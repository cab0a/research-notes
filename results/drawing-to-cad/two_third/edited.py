# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.
from research_notes.drawing_to_cad import export_candidate
PARAMETERS = {'holes': [{'diameter': 6.0, 'x': 28.0, 'y': 21.0}, {'diameter': 5.0, 'x': 11.0, 'y': 8.0}], 'length': 30.0, 'thickness': 10.0, 'width': 45.0}
SOURCE_SHA256 = 'c3abb5c8f52a888086afcf36e85f421fd2c0e2e1c8afcb8d2ecaf8706fbb3cf0'
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('step')
    args = parser.parse_args()
    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)

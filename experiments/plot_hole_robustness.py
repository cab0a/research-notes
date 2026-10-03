"""Plot frozen STEP edges and accepted walls from the v1.12 study."""
import argparse
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=Path('results/hole-robustness'))
    parser.add_argument('--fixtures',type=Path,default=Path('fixtures/hole-robustness'))
    args=parser.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopAbs import TopAbs_EDGE,TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from research_notes.brep_runtime import indexed_shapes,iter_shapes
    from research_notes.public_step import read_step_for_inspection
    report=json.loads((args.results/'results.json').read_text())
    records={r['id']:r['result'] for r in report['records'] if r['path']=='unified'}
    examples=[('mixed','Qualified: one round hole + one slot'),
              ('circle_rectangular_shoulder','Rectangular counter-recess: withheld'),
              ('slot_blind','Blind capsule pocket: withheld'),
              ('assembly_obstructed','Separate cap: local holes remain\nAssembly clearance is not checked')]
    fig=plt.figure(figsize=(13,9),layout='constrained')
    for panel,(identifier,title) in enumerate(examples,1):
        shape=read_step_for_inspection(args.fixtures/'sources'/f'{identifier}.step').imported.shape
        edges=indexed_shapes(shape,TopAbs_EDGE);faces=indexed_shapes(shape,TopAbs_FACE)
        highlight={}
        for hole in records[identifier]['holes']:
            color='#cc8927' if hole['feature_type']=='circular_hole' else '#128a8b'
            for face_id in hole['faces']:
                for edge in iter_shapes(faces.FindKey(face_id),TopAbs_EDGE):
                    highlight[edges.FindIndex(edge)]=color
        ax=fig.add_subplot(2,2,panel,projection='3d')
        for i in range(1,edges.Extent()+1):
            curve=BRepAdaptor_Curve(TopoDS.Edge_s(edges.FindKey(i)))
            points=[curve.Value(curve.FirstParameter()+u*(curve.LastParameter()-curve.FirstParameter())).Coord()
                    for u in [j/48 for j in range(49)]]
            ax.plot(*zip(*points),color=highlight.get(i,'#8d9aa2'),lw=1.5 if i in highlight else .7)
        ax.set(title=title,xlabel='X (mm)',ylabel='Y (mm)',zlabel='Z (mm)')
        for axis in (ax.xaxis,ax.yaxis,ax.zaxis):
            axis.set_major_locator(MaxNLocator(4))
        ax.set_box_aspect((3.6 if identifier in {'mixed','assembly_obstructed'} else 1.4,1,.55))
        ax.view_init(elev=28,azim=-62)
    fig.suptitle('v1.12.0: frozen STEP examples and conservative recognition\nAmber = qualified round walls; teal = qualified slot walls; whole counts remain unknown',fontsize=13)
    fig.savefig(args.results/'examples.png',dpi=150)
    plt.close(fig)


if __name__=='__main__':
    main()

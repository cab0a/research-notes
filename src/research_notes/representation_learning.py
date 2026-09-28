"""Small deterministic multiclass centroids with validation-only calibration."""
from __future__ import annotations
import math
from dataclasses import asdict,dataclass
import numpy as np


@dataclass(frozen=True)
class RepresentationModel:
    labels:tuple[str,...]
    means:tuple[float,...]
    scales:tuple[float,...]
    centroids:tuple[tuple[float,...],...]
    temperature:float
    feature_names:tuple[str,...]
    train_ids:tuple[str,...]
    validation_ids:tuple[str,...]
    abstention_threshold:float=.7


def _probabilities(distances,temperature):
    logits=-np.array(distances)/temperature;logits-=np.max(logits)
    p=np.exp(logits);return p/p.sum()


def fit_representation(rows,feature_names):
    rows=tuple(rows);train=[r for r in rows if r["split"]=="train"];validation=[r for r in rows if r["split"]=="validation"]
    if not train or not validation:raise ValueError("training and validation records required")
    owners={}
    for r in rows:
        if r["split"] not in {"train","validation","test"}:raise ValueError("unknown split")
        owners.setdefault(r["lineage_id"],set()).add(r["split"])
    if any(len(s)>1 for s in owners.values()):raise ValueError("cross-split derivation leakage")
    x=np.array([r["values"] for r in train],dtype=float)
    if x.ndim!=2 or x.shape[1]!=len(feature_names) or x.shape[1]>128 or not np.isfinite(x).all():raise ValueError("invalid feature matrix")
    labels=tuple(sorted({r["truth"] for r in train}))
    if len(labels)<2:raise ValueError("at least two training classes required")
    mean=x.mean(axis=0);scale=x.std(axis=0);scale=np.where(scale<1e-9,1.,scale)
    z=(x-mean)/scale
    centroids=np.array([z[[r["truth"]==label for r in train]].mean(axis=0) for label in labels])
    val=np.array([r["values"] for r in validation],dtype=float)
    if val.shape!=(len(validation),len(feature_names)) or not np.isfinite(val).all() or any(r["truth"] not in labels for r in validation):raise ValueError("invalid validation matrix/labels")
    distances=((val[:,None,:]-mean)/scale-centroids[None,:,:])**2
    distances=distances.sum(axis=2)
    losses=[]
    for temperature in (.25,.5,1.,2.,4.,8.,16.):
        loss=-sum(math.log(max(_probabilities(d,temperature)[labels.index(r["truth"])],1e-15)) for d,r in zip(distances,validation))/len(validation)
        losses.append((loss,temperature))
    temperature=min(losses)[1]
    return RepresentationModel(labels,tuple(mean),tuple(scale),tuple(map(tuple,centroids)),temperature,tuple(feature_names),
                               tuple(r["sample_id"] for r in train),tuple(r["sample_id"] for r in validation))


def predict_representation(model,values):
    values=np.array(values,dtype=float)
    if values.shape!=(len(model.means),) or not np.isfinite(values).all():raise ValueError("invalid prediction vector")
    z=(values-model.means)/model.scales
    per_feature=(z-np.array(model.centroids))**2;distances=per_feature.sum(axis=1);p=_probabilities(distances,model.temperature)
    order=np.argsort(-p,kind="stable");winner=int(order[0]);second=int(order[1]);confidence=float(p[winner])
    margin=per_feature[second]-per_feature[winner]
    # Out-of-range descriptors retain scores but do not become confident decisions.
    out_of_domain=bool(np.max(np.abs(z))>10.)
    decision="abstain" if out_of_domain or confidence<model.abstention_threshold else model.labels[winner]
    return {"ranking":[{"label":model.labels[i],"probability":float(p[i]),"squared_distance":float(distances[i])} for i in order],
            "prediction":model.labels[winner],"confidence":confidence,"decision":decision,"out_of_domain":out_of_domain,
            "influence":[{"feature":name,"value":float(value),"winner_vs_runner_distance_margin":float(contribution)} for name,value,contribution in zip(model.feature_names,values,margin)],
            "confidence_kind":"validation-temperature-scaled synthetic centroid probability"}


def prediction_metrics(rows):
    if not rows:raise ValueError("empty evaluation")
    decided=[r for r in rows if r["decision"]!="abstain"]
    correct=[r["prediction"]==r["truth"] for r in rows]
    ece=0.
    for low,high in ((0.,.5),(.5,.7),(.7,.9),(.9,1.000001)):
        bucket=[r for r in rows if low<=r["confidence"]<high]
        if bucket:ece+=len(bucket)/len(rows)*abs(sum(r["confidence"] for r in bucket)/len(bucket)-sum(r["prediction"]==r["truth"] for r in bucket)/len(bucket))
    brier=sum(sum((item["probability"]-int(item["label"]==r["truth"]))**2 for item in r["ranking"]) for r in rows)/len(rows)
    return {"count":len(rows),"accuracy":sum(correct)/len(rows),"coverage":len(decided)/len(rows),
            "selective_accuracy":sum(r["prediction"]==r["truth"] for r in decided)/len(decided) if decided else None,
            "brier":brier,"expected_calibration_error":ece,
            "high_confidence_errors":[r["sample_id"] for r in rows if r["confidence"]>=.7 and r["prediction"]!=r["truth"]]}

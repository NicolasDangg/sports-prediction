"""E006 diagnostic (post-hoc, not a pass rule): does the E006 model add anything ON TOP of the market?

Blend logit(bookmaker) and logit(model) with a logistic regression. Each 2020-22 year is scored by a
blend fitted on the other two years. If the model knew something the odds don't, it would get a
clear positive weight and the blend would beat the bookmaker alone.

    uv run --group experiments python -W ignore experiments/e006_market_blend.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "experiments")]  # noqa: E401
import numpy as np, pandas as pd, backtest as bt  # noqa: E402
from sklearn.linear_model import LogisticRegression
import e006_serve_stats as e
from e004_format_calibration import cluster_ci, match_ll
from strategies import logit
df=bt.load_atp(); df["best_of"]=df["Best of"]
f=e.build_features(df); f["elo_logit"]=logit(f.elo_p.to_numpy())
f["tourney"]=df.date.dt.year.astype(str).to_numpy()+" "+df.Tournament.to_numpy()
st,_=e.stat_features(df); f=pd.concat([f,st],axis=1); y=f.p1_won.astype(int).to_numpy()
p,_,_=e.fit_and_score("E006",f,e.BASE+e.NEW,y)
va=f.date.between(*e.VALID).to_numpy(); v=f[va].reset_index(drop=True); yv=y[va]
ok=((v.odd_1>1)&(v.odd_2>1)).to_numpy(); v,yv,p=v[ok].reset_index(drop=True),yv[ok],p[ok]
book=bt.implied_probs(v[["odd_1","odd_2"]].to_numpy(float))[:,0]
X=np.column_stack([logit(book),logit(p)]); yr=v.date.dt.year.to_numpy()
blend=np.empty(len(v)); coefs=[]
for Y in (2020,2021,2022):
    m=LogisticRegression(fit_intercept=False,C=1e6).fit(X[yr!=Y],yv[yr!=Y]); coefs.append(m.coef_[0].round(3).tolist())
    blend[yr==Y]=m.predict_proba(X[yr==Y])[:,1]
d=match_ll(book,yv)-match_ll(blend,yv); ci=cluster_ci(d,v.tourney.to_numpy())
print("weights [market, model] per held-out year:",coefs)
print(f"log loss bookmaker {match_ll(book,yv).mean():.4f}  blend {match_ll(blend,yv).mean():.4f}  improvement {d.mean():+.5f} CI [{ci[0]:+.5f},{ci[1]:+.5f}]")

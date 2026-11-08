"""World state, lightweight hypothetical branching and predictive calibration."""
from dataclasses import dataclass,asdict
from copy import deepcopy
from typing import Any

@dataclass
class Scenario:
    name: str
    state: dict
    value: float
    uncertainty: float
    cost: float
    risk: float
    permitted: bool
    score: float


class WorldModel:
    """No claims of physical certainty. Transition forecasts are explicitly hypothetical."""
    def simulate(self, state: dict, change: dict, *, value=.5, uncertainty=.5, cost=.1, risk=.1,
                 permitted=False, name='candidate'):
        values=[value,uncertainty,cost,risk]
        if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and 0<=v<=1 for v in values):
            raise ValueError('scores must be normalized numbers between 0 and 1')
        snapshot=deepcopy(state)
        snapshot.update(deepcopy(change))
        score=(float(value)-.35*float(uncertainty)-.30*float(cost)-.55*float(risk))
        if not permitted:
            score=float('-inf')
        return Scenario(name,snapshot,value,uncertainty,cost,risk,permitted,score)

    def compare(self,state,alternatives):
        scenarios=[self.simulate(state,a.get('changes',{}),name=a.get('name','alternative'),
                                 value=a.get('value',.5),uncertainty=a.get('uncertainty',.5),
                                 cost=a.get('cost',.1),risk=a.get('risk',.1),
                                 permitted=a.get('permitted',False)) for a in alternatives]
        return [asdict(s) for s in sorted(scenarios,key=lambda s:s.score,reverse=True)]

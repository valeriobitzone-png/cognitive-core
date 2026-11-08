"""Host-agnostic hybrid world model selector: validated learned dynamics or evidence-backed discrete transitions.

The interface accepts any finite structured environment, but it only predicts
when a trained compatible model supports the requested state and action.
"""
from __future__ import annotations
from .worldmodel import _valid_atom

class HybridWorldMixin:
    def predict_world_state(self,owner,environment,before,action,*,space='default',family=None):
        """Route to bounded learned model, otherwise to empirical v0.6 frequencies.

        No execution and no hallucinated prediction for completely unknown worlds.
        """
        owner,space,environment,action=[_valid_atom(v,'identifier') for v in (owner,space,environment,action)]
        if family and isinstance(before,dict) and before and all(type(v) in (int,float) for v in before.values()):
            learned=self.predict_shared_dynamics(owner,family,before,action,space=space)
            if learned['status']=='predicted':
                return {**learned,'method':'cross_environment_numeric_dynamics',
                        'world':environment,'action':action,'action_executed':False}
        empirical=self.imagine_world(owner,environment,before,[action],space=space,max_branches=3)
        if empirical['status']=='simulated':
            states=empirical['steps'][0]['states']
            return {'status':'predicted','method':'observed_discrete_frequency',
                    'world':environment,'action':action,'candidates':states,
                    'warning':'Observed conditional frequencies are not causal dynamics','action_executed':False}
        return {'status':'abstain','reason':'no_compatible_verified_world_model',
                'world':environment,'action':action,'action_executed':False}

    def simulate_hybrid_world(self,owner,environment,before,actions,*,space='default',family=None):
        """Bounded, unbranched chain. Step-only; uncertainty grows through each step."""
        from .engine import WorldCoreError
        if not isinstance(actions,list) or not 1<=len(actions)<=8:raise WorldCoreError('1..8 actions required')
        state=before;steps=[]
        for act in actions:
            pred=self.predict_world_state(owner,environment,state,act,space=space,family=family)
            if pred['status']!='predicted':
                return {'status':'abstain','at_step':len(steps),'trajectory':steps,
                        'reason':pred['reason'],'action_executed':False}
            if pred['method']=='observed_discrete_frequency':
                selected=pred['candidates'][0]
                state=selected['state'];evidence={'model':'discrete','probability':selected['likelihood']}
            else:
                state=pred['state'];evidence={'model':'learned_numeric','version':pred['model_version'],
                                               'heldout_mae':pred['holdout_mae']}
            steps.append({'action':act,'state':state,'evidence':evidence})
        return {'status':'simulated','trajectory':steps,'action_executed':False,
                'warning':'Rollout error compounds. No universal environment understanding or safety guarantee.'}

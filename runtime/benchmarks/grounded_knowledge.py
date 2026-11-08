"""Operator-curated ORIGINAL summaries of checked public source pages (not copied articles).

The citations are source attribution, not proof that an LLM learned a foundation model.
The benchmark measures retrieval only, and its questions were written by the same
editor as the summaries, so it is not a blind human-rated QA benchmark.
"""
from __future__ import annotations
import json
from pathlib import Path
from worldcore import WorldCore

SOURCES = [
('hermes_hooks','Hermes event lifecycle hooks','https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/index.md','MIT',
 'Hermes Agent exposes Python plugin lifecycle hooks including pre_llm_call for additional context, post_tool_call for outcome observation, and pre_tool_call for guardrails. A memory helper can supply context, but a plugin callback is not equivalent to a safe autonomous permission system. The host itself remains responsible for execution and authorisation. A callback error can be handled by the host without taking the agent offline. Context must be identified as untrusted evidence, not as an instruction.'),
('hermes_plugins','Hermes plugin categories','https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/plugins.md','MIT',
 'Hermes supports general plugins, replacement memory providers, context-engine providers and model-provider integrations. General plugins register tool and lifecycle functionality. Memory providers can replace or extend a built-in memory mechanism. A plugin can observe events from the runtime, although permitted callbacks depend on the active Hermes release and host configuration. Do not assume automatic account authentication simply because plugin hooks exist.'),
('openclaw_sdk','OpenClaw plugin SDK','https://github.com/openclaw/openclaw/blob/main/LICENSE','MIT',
 'OpenClaw has a plugin SDK with host lifecycle hooks, agent tools, services, and memory or context capability slots. Integration must be version pinned and tested against a real OpenClaw Gateway, because mock hook invocations alone do not show complete compatibility. Native plugin hooks are often needed for automatic event collection. An MCP server is useful for universal tool calls but cannot guarantee observing every host action.'),
('uci_iris','Iris flower dataset','https://uci-ics-mlr-prod.aws.uci.edu/dataset/53/iris','CC-BY-4.0',
 'The Iris dataset contains 150 genuine flower observations and four measured attributes: sepal length, sepal width, petal length and petal width. Its three categories are Setosa, Versicolour and Virginica. It is a small supervised classification benchmark, not a measure of general reasoning. Its publisher is the UCI Machine Learning Repository. The original dataset is associated with the work of Ronald A Fisher.'),
('uci_wine','Italian wine chemical dataset','https://uci-ics-mlr-prod.aws.uci.edu/dataset/109/wine','CC-BY-4.0',
 'The UCI Wine dataset contains chemical measurement vectors for 178 samples produced from three cultivars in the same region of Italy. Thirteen numerical chemical attributes include alcohol, malic acid, flavanoids, colour intensity, phenols and proline. The model can use these measurements to distinguish cultivar categories. It is suitable for simple supervised classification and cannot teach an agent broad world knowledge.'),
('uci_digits','Handwritten digits dataset','https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits','CC-BY-4.0',
 'The Optical Recognition of Handwritten Digits collection includes handwritten numerals and numerical pixel measurements. The scikit-learn packaged subset offers 1797 samples with 8 by 8 pixel representations. A binary classification experiment can label digits five through nine versus digits zero through four. These samples evaluate pattern recognition on images, not autonomous planning or world-model causality.'),
('uci_winequality','Wine quality scores','https://archive.ics.uci.edu/dataset/186/wine+quality','CC-BY-4.0',
 'The separate UCI Wine Quality dataset contains Portuguese red and white wine measurements and expert sensory scores. Its physicochemical predictors include fixed and volatile acidity, sulphates, alcohol, sugar and pH. It should not be confused with the Italian Wine cultivar dataset. Data originate from the research of Cortez and colleagues and are published by UCI under Creative Commons Attribution.'),
('uci_retail','Online retail transaction dataset','https://uci-ics-mlr-prod.aws.uci.edu/dataset/352/online+retail','CC-BY-4.0',
 'The UCI Online Retail dataset describes transactions of a UK-based internet retailer over 2010 and 2011. Fields include invoice number, product stock code, item description, unit price, order quantity and customer information. It has over half a million line items. It can support studies of purchase patterns, cancellations and seasonal transactions, but should be handled with care because it contains customer identifiers.'),
('stats_sunspots','Historical solar activity','https://www.statsmodels.org/v0.13.5/datasets/generated/sunspots.html','PUBLIC-DOMAIN',
 'The public-domain sunspot series bundled with statsmodels reports yearly observed solar activity from 1700 through 2008, a total of 309 years. A chronological split provides a more realistic forecasting benchmark than random rows from the same sequence. Solar activity is periodic and noisy. A statistical learner must be evaluated against constant and persistence baselines; high in-sample fit alone cannot prove forecasting success.'),
('stats_macrodata','United States macroeconomic quarterly history','https://www.statsmodels.org/0.8.0/datasets/generated/macrodata.html','PUBLIC-DOMAIN',
 'The public-domain statsmodels macrodata collection contains United States quarterly indicators from 1959 Q1 through 2009 Q3. It draws on Federal Reserve Economic Data and Bureau of Labor Statistics sources. Variables include real gross domestic product, inflation, unemployment, consumption and investment. Chronological evaluation is needed to avoid leakage from future economic conditions. These historic records cannot support claims about current markets.'),
('stats_co2','Mauna Loa atmospheric carbon dioxide measurements','https://www.statsmodels.org/dev/datasets/generated/co2.html','PUBLIC-DOMAIN',
 'The public-domain statsmodels Mauna Loa carbon dioxide series covers historical weekly readings over 1958 to 2001, with some absent measurements. Predictors may describe measured concentrations, week-of-year seasonality and recent changes. Missing data should use a past-only forward fill to avoid future-data leakage. A trend in carbon dioxide measurements is not itself a model of physical interventions.'),
('sira_architecture','SiRA simulative reasoning architecture','https://github.com/sailing-lab/sira','APACHE-2.0',
 'SiRA is a research architecture for agent planning using simulated future states. It separates an encoder that represents observations, a policy that proposes candidates, a world model that predicts consequences, a critic that evaluates goal progress and an actor that executes chosen actions. Its released implementation targets browser environments. The repository does not supply general world-model training code or demonstrate AGI.'),
('conversation_objective','WorldCore user-requested product direction','conversation://current/worldcore-goal','USER-PROVIDED',
 'The operator asked for WorldCore to remain independent from other agent frameworks, while connecting to Hermes, OpenClaw, MONO and other hosts. Its desired long-term capabilities include accurate persistent memory, proactive need identification, counterfactual planning, verifiable predictions, and continual learning through observed results. API keys and consumer subscriptions should remain handled by official supported host integrations.'),
('conversation_evaluation','WorldCore user-requested validation policy','conversation://current/worldcore-validation','USER-PROVIDED',
 'The operator asked for WorldCore to be tested in a sandbox and delivered only when verified. Synthetic results alone are insufficient to establish general intelligence. Tests should include external data, held-out evaluations, persistence, performance, security, and real host integration. Avoid pretending the ChatGPT pretrained corpus is available to export and do not assert infinite asynchronous training.'),
]

CASES = [
('Which Hermes hook can add memory context before an LLM call?','hermes_hooks'),
('Where are Hermes memory providers and model providers defined?','hermes_plugins'),
('What plugin sdk does OpenClaw use for its Gateway and memory slots?','openclaw_sdk'),
('How many flower samples and sepal attributes are in Iris?','uci_iris'),
('Which Italian wines have cultivar labels and proline?','uci_wine'),
('Which dataset has handwritten numeral pixel blocks 8 by 8?','uci_digits'),
('Which Portugal wine quality scores measure pH and volatile acidity?','uci_winequality'),
('Which transactions have invoice, stock and quantity fields?','uci_retail'),
('What series records sunspot activity since the year 1700?','stats_sunspots'),
('Where are quarterly United States real GDP and unemployment indicators?','stats_macrodata'),
('Which public dataset covers weekly Mauna Loa atmospheric carbon dioxide?','stats_co2'),
('Which architecture uses encoder policy world model critic and actor?','sira_architecture'),
('Which project goal requires portability across Hermes and OpenClaw?','conversation_objective'),
('Which user policy requires sandbox validation before release?','conversation_evaluation'),
]

def seed(w: WorldCore):
    for doc_id,title,url,license,text in SOURCES:
        owner='user_project' if url.startswith('conversation:') else 'public_research'
        space='project' if owner=='user_project' else 'web_evidence'
        w.ingest_document(owner,doc_id,text,space=space,title=title,source_url=url,license=license)

def run(db: Path, output: Path):
    with WorldCore(db) as w:
        seed(w)
        public=[{'query':q,'expected_document':d} for q,d in CASES if not d.startswith('conversation_')]
        private=[{'query':q,'expected_document':d} for q,d in CASES if d.startswith('conversation_')]
        eval1=w.evaluate_retrieval('public_research',public,space='web_evidence',k=3)
        eval2=w.evaluate_retrieval('user_project',private,space='project',k=3)
        combined={'public_sources':w.knowledge_stats('public_research',space='web_evidence'),
                  'user_project':w.knowledge_stats('user_project',space='project'),
                  'retrieval_public':eval1,'retrieval_project':eval2,
                  'note':'Small editor-written retrieval check, not unseen blind QA or language-model training',
                  'sources':[{'id':r[0],'url':r[2],'license':r[3]} for r in SOURCES]}
        output.write_text(json.dumps(combined,ensure_ascii=False,indent=2))
    return combined
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(run(Path(a.db),Path(a.output)),indent=2)[:900])

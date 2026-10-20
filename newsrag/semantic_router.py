"""Primary operation recognition using local question embeddings.

Examples describe operations, never answers or corpus membership. A small matrix
is sufficient here; the persistent Chroma collection remains the article index.
"""
import re
import numpy as np
EXAMPLES = {
    'ai': ('Summarize artificial intelligence developments in the news.',
           'Give an overview of machine learning stories.',
           'What are the main stories about AI technology?'),
    'funding': ('Which startups raised money and how much?',
                'List companies that secured venture investment recently.',
                'Which businesses received financial backing?',
                'Show recently financed startups and their funding amounts.'),
    'company': ('What has Acme announced recently?',
                'Tell me about Acme Corporation product launches.',
                'What is new at Example Systems?'),
    'location': ('Find every article mentioning the city of Pune.',
                 'Which stories refer to New Delhi?',
                 'Show all reports that name Bengaluru.'),
    'layoffs': ('Which companies announced job cuts this month?',
                'Summarize reports of employees being let go.',
                'Find news about workforce reductions.'),
    'investors': ('Which investors participated in more than one funding round?',
                  'Identify backers shared by different investment rounds.',
                  'Who repeatedly financed startups in this collection?'),
    'revenue': ('What revenue does the article "Quarterly results" report?',
                'Find the sales turnover figure in this article.',
                'How much revenue did the company report in this story?'),
    'unsupported': ('What is the weather forecast for Mumbai?',
                    'Write a poem about startups.',
                    'Should I invest in this company?',
                    'Predict the next funding round.',
                    'Explain how to raise venture capital.',
                    'Who won the cricket match?',
                    'What is the stock price right now?',
                    'How do I build a machine learning model?'),
}

# Operation descriptions/prototypes, not keyword dictionaries or stored answers.
# Evaluation questions live separately in tests/data/semantic_questions.json.
EXAMPLES['ai'] += (
    'Brief me on recent progress in intelligent computer systems.',
    'Summarize the latest developments in AI research and applications.',
    'Show news about how artificial intelligence is being used.',
    'What new AI technologies are businesses adopting?',
    'Give me an overview of AI announcements across the collection.',
)
EXAMPLES['funding'] += (
    'Identify companies that completed capital raises.',
    'Report the startup funding recipients and amounts raised.',
    'Which new businesses have been funded by investors?',
    'What investments have startups secured this week?',
    'Which startups received money from multiple investors?',
    'Show venture financing received by businesses in a city.',
)
EXAMPLES['company'] += (
    'Bring me the things the company has put out lately.',
    'Describe the latest offerings released by this business.',
    'What has the company announced recently?',
    'Summarize the products and services a company has unveiled.',
    'What did this business announce to its customers?',
    'Which new products did the specified firm release?',
    'Give me recent updates concerning one named corporation.',
    'What has Example AI announced about its new products?',
    'Show recent company announcements from Example Systems.',
)
EXAMPLES['location'] += (
    'List every article containing a particular location name.',
    'Find all news articles with references to this city.',
    'Which articles mention the named place in their text?',
    'Return all the stories that refer to a given location.',
    'Find news mentioning a country or a city.',
)
EXAMPLES['layoffs'] += (
    'Summarize the layoff news in the collection.',
    'Give me reports of layoffs and staff reductions this month.',
    'What layoff announcements have employers made?',
    'Summarise news about layoffs.',
    'Which businesses are dismissing employees?',
    'Report on companies making staff redundant.',
    'Summarize employment losses and corporate downsizing.',
    'Which firms are eliminating jobs and reducing their teams?',
    'Find coverage about businesses cutting the number of employees.',
)
EXAMPLES['investors'] += (
    'Count how many separate financing rounds each investor joined.',
    'Which investors participated in a single funding round?',
    'Which capital providers participated in two or three rounds?',
    'Identify investors who financed a specific number of companies.',
    'Find the investors who backed multiple startup businesses.',
    'Which venture funds have made investments across distinct deals?',
    'Name backers whose participation occurs in several financing rounds.',
)
EXAMPLES['revenue'] += (
    'What numerical sales income is reported in the selected article?',
    'Find the revenue amount, growth or forecast in this report.',
    'How much did the business earn according to this article?',
    'Quote what the named article says about business revenue.',
    'What were the sales figures in the article with this title?',
)
EXAMPLES['unsupported'] += (
    'Teach me how to construct and train an intelligent software application.',
    'Provide a tutorial for building neural networks.',
    'Explain the steps needed to develop an AI algorithm.',
    'Invent a fictional account of a startup obtaining investment.',
    'Compose an imaginary news story involving investors and new technology.',
    'Create an entertaining narrative about venture capital and machine learning.',
    'Is the subject investment or employee dismissals?',
    'Decide whether this question is asking about capital or staffing.',
    'Tell me which of the different news categories this belongs to.',
    'Make up a story about a company announcing job cuts.',
    'Forecast future layoffs at technology companies.',
    'Recommend profitable investments and calculate my future returns.',
    'Compare revenue with layoffs and funding across all companies.',
    'Answer unrelated general knowledge questions.',
)

TRAINING_ENTITIES = {
    'companies': ('Acme Corporation', 'Acme', 'Example Systems', 'Example AI'),
    'locations': ('Pune', 'New Delhi', 'Bengaluru', 'Mumbai'),
}


class SemanticRouter:
    # Regularized linear classification over normalized sentence embeddings.
    # Scores are uncalibrated classifier outputs, never probabilities/cosines.
    regularization = 0.3
    minimum_score = 0.30
    minimum_margin = 0.05
    unsupported_conflict_score = 0.38

    def __init__(self, embedder):
        self.embedder = embedder
        self.labels = [label for label, texts in EXAMPLES.items() for _ in texts]
        self.vectors = embedder.encode([self.prepare(text, TRAINING_ENTITIES)
                                        for texts in EXAMPLES.values() for text in texts])
        self.classes = list(EXAMPLES)
        targets = np.array([[float(label == category) for category in self.classes]
                            for label in self.labels], dtype=np.float64)
        kernel = self.vectors @ self.vectors.T
        self.coefficients = np.linalg.solve(kernel + self.regularization*np.eye(len(self.labels)), targets)

    @staticmethod
    def prepare(question, entities=None):
        text = re.sub(r'["“][^"”]*["”]', 'the selected article', question)
        # Corpus names are slots, not evidence for the requested operation.
        names = {}
        company_names = {name.casefold() for name in (entities or {}).get('companies', ())}
        location_names = {name.casefold() for name in (entities or {}).get('locations', ())}
        ambiguous_names = company_names & location_names
        for field, replacement in (('companies', 'the company'), ('locations', 'the location')):
            for name in (entities or {}).get(field, ()):
                # A model can put a country in both catalogs. Preserve the name
                # rather than injecting an arbitrary entity type into the query.
                if len(name.strip()) >= 3 and name.casefold() not in ambiguous_names:
                    names.setdefault(name, replacement)
        if names:
            alternatives = [r'(?-i:' + re.escape(n) + ')' if n.isupper() and len(n) <= 4 else re.escape(n)
                            for n in sorted(names, key=len, reverse=True)]
            pattern = re.compile(r'(?<!\w)(?:' + '|'.join(alternatives) + r')(?!\w)', re.I)
            folded = {name.casefold(): replacement for name, replacement in names.items()}
            text = pattern.sub(lambda match: folded[match.group().casefold()], text)
        return text

    def classify(self, question, *, entities=None):
        text = self.prepare(question, entities)
        similarities = self.embedder.encode([text])[0] @ self.vectors.T
        outputs = similarities @ self.coefficients
        scores = dict(zip(self.classes, map(float, outputs)))
        return self.decide(scores, text)

    @classmethod
    def decide(cls, scores, text):
        ranked = sorted(scores, key=scores.get, reverse=True)
        winner, runner_up = ranked[:2]
        score, margin = scores[winner], scores[winner] - scores[runner_up]
        accepted = score >= cls.minimum_score and margin >= cls.minimum_margin
        reason = None if accepted else 'weak or competing operation scores'
        if winner != 'unsupported' and scores.get('unsupported', 0) >= cls.unsupported_conflict_score:
            accepted = False
            reason = 'substantial competing unsupported-request score'
        return {'intent': winner if accepted else 'unsupported', 'candidate': winner,
                'score': score, 'margin': margin, 'accepted': accepted, 'scores': scores,
                'normalized_question': text, 'version': 'semantic-primary-v2',
                'regularization': cls.regularization, 'score_kind': 'uncalibrated ridge classifier output',
                'abstention_reason': reason,
                'method': 'primary local MiniLM embeddings and regularized operation classifier; no generative model'}

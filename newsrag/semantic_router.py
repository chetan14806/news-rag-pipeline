"""Conservative local question-to-question similarity for unresolved intents.

Examples describe operations, never answers or corpus membership. A small matrix
is sufficient here; the persistent Chroma collection remains the article index.
"""
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


class SemanticRouter:
    # Cosine scores are similarities, not probabilities. Conservative development
    # cutoffs deliberately abstain on weak matches and competing operations.
    minimum_score = 0.55
    minimum_margin = 0.08

    def __init__(self, embedder):
        self.embedder = embedder
        self.labels = [label for label, texts in EXAMPLES.items() for _ in texts]
        self.vectors = embedder.encode([text for texts in EXAMPLES.values() for text in texts])

    def classify(self, question):
        similarities = self.vectors @ self.embedder.encode([question])[0]
        scores = {label: max(float(score) for candidate, score in zip(self.labels, similarities)
                             if candidate == label) for label in EXAMPLES}
        ranked = sorted(scores, key=scores.get, reverse=True)
        winner, runner_up = ranked[:2]
        score, margin = scores[winner], scores[winner] - scores[runner_up]
        accepted = score >= self.minimum_score and margin >= self.minimum_margin
        return {'intent': winner if accepted else 'unsupported', 'candidate': winner,
                'score': score, 'margin': margin, 'accepted': accepted,
                'method': 'local MiniLM question similarity; no generative model'}

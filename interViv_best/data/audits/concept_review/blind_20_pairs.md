# Twenty pairs for independent labeling

No assistant labels are included. Answer excerpts retain the complete supplied answer to avoid removing relevant evidence. Similarity is a model diagnostic, not a correctness probability.

## R01: classification (Tier 3)

**Question:** Explain how a decision tree works.

**Answer excerpt:** A decision tree splits data using rules. At each step it picks the feature that best separates the data. The leaves give the final predictions.

**Similarity:** 0.5674

**Your label:**

**Your notes:**

## R02: regression (Tier 3)

**Question:** Explain how a decision tree works.

**Answer excerpt:** A decision tree splits data at each node based on a feature threshold that best separates the classes. It recurses until reaching leaf nodes which give the prediction. Decision trees are easy to interpret but can overfit. Random forests use many trees together.

**Similarity:** 0.5202

**Your label:**

**Your notes:**

## R03: overfitting (Tier 3)

**Question:** What is the bias-variance tradeoff?

**Answer excerpt:** Bias is error from wrong assumptions in the model — high bias models are too simple, underfit, perform poorly on training and test data. Variance is sensitivity to fluctuations. Some additional details apply.

**Similarity:** 0.5606

**Your label:**

**Your notes:**

## R04: cross-validation (Tier 3)

**Question:** What is the bias-variance tradeoff?

**Answer excerpt:** Bias is error from wrong assumptions in the model — high bias models are too simple, underfit, perform poorly on training and test data. Variance is sensitivity to fluctuations. Some additional details apply.

**Similarity:** 0.4114

**Your label:**

**Your notes:**

## R05: STAR (Tier 3)

**Question:** How do you handle conflict with a coworker?

**Answer excerpt:** I first try to understand their perspective directly in a private conversation rather than escalating. I listen fully before responding and focus on the specific issue not the person. If we disagree technically, I suggest we both write up our approaches and evaluate them against agreed criteria. I find that conflicts often come from different context or assumptions, and direct conversation resolves most of them.

**Similarity:** 0.2313

**Your label:**

**Your notes:**

## R06: action (Tier 3)

**Question:** How do you handle conflict with a coworker?

**Answer excerpt:** I first try to understand their perspective directly in a private conversation rather than escalating. I listen fully before responding and focus on the specific issue not the person. If we disagree technically, I suggest we both write up our approaches and evaluate them against agreed criteria. I find that conflicts often come from different context or assumptions, and direct conversation resolves most of them.

**Similarity:** 0.3783

**Your label:**

**Your notes:**

## R07: communication (Tier 3)

**Question:** How do you handle conflict with a coworker?

**Answer excerpt:** I first try to understand their perspective directly in a private conversation rather than escalating. I listen fully before responding and focus on the specific issue not the person. If we disagree technically, I suggest we both write up our approaches and evaluate them against agreed criteria. I find that conflicts often come from different context or assumptions, and direct conversation resolves most of them.

**Similarity:** 0.6107

**Your label:**

**Your notes:**

## R08: key distribution (Tier 2)

**Question:** What is the difference between symmetric and asymmetric encryption?

**Answer excerpt:** Symmetric uses same key for encrypt and decrypt. Asymmetric uses public and private key. Asymmetric is slower but more secure for sharing keys.

**Similarity:** 0.5921

**Your label:**

**Your notes:**

## R09: caching (Tier 3)

**Question:** How would you design a search engine?

**Answer excerpt:** A search engine needs a crawler to fetch pages, an indexer to build an inverted index of terms to documents, and a ranking algorithm to sort results. Elasticsearch uses Lucene for indexing. Distributed sharding handles large document sets.

**Similarity:** 0.3481

**Your label:**

**Your notes:**

## R10: caching (Tier 3)

**Question:** How would you design a search engine?

**Answer excerpt:** Crawler: politeness (robots.txt, rate limiting), deduplication via URL hashing. Indexer: tokenisation, stemming, stop-word removal, positional inverted index. Ranking: BM25 for relevance, PageRank for authority, click signals. Serving: query parsing, index lookup, scoring, snippet generation. Scale: partition index by document range; federate queries. Elasticsearch uses multiple shards and replicas, Lucene segments merged in background.

**Similarity:** 0.3248

**Your label:**

**Your notes:**

## R11: bagging (Tier 3)

**Question:** What is a random forest?

**Answer excerpt:** A random forest trains many decision trees on random subsets of data and features, then aggregates their predictions. This ensemble approach reduces overfitting compared to a single tree. Feature importance is calculated as average reduction in impurity.

**Similarity:** 0.3009

**Your label:**

**Your notes:**

## R12: regression (Tier 3)

**Question:** What is a random forest?

**Answer excerpt:** A random forest trains many decision trees on random subsets of data and features, then aggregates their predictions. This ensemble approach reduces overfitting compared to a single tree. Feature importance is calculated as average reduction in impurity.

**Similarity:** 0.43

**Your label:**

**Your notes:**

## R13: unstructured (Tier 2)

**Question:** What is the difference between Azure Blob Storage, Azure File Storage, and Azure Queue Storage?

**Answer excerpt:** Blob is for files like images. File storage is like a file server you can mount. Queue is for messages between services.

**Similarity:** 0.3015

**Your label:**

**Your notes:**

## R14: asynchronous (Tier 2)

**Question:** What is the difference between Azure Blob Storage, Azure File Storage, and Azure Queue Storage?

**Answer excerpt:** Blob is for files like images. File storage is like a file server you can mount. Queue is for messages between services.

**Similarity:** 0.4139

**Your label:**

**Your notes:**

## R15: random forest (Tier 3)

**Question:** Explain how a decision tree works.

**Answer excerpt:** At each node, the tree picks the feature-threshold pair that maximises information gain (entropy reduction) or minimises Gini impurity. It recurses on each child subset. Stopping criteria: max depth, min samples per leaf, no remaining gain. Predictions: leaf's majority class (classification) or mean (regression). Trees are interpretable, handle mixed types, require no scaling, but overfit. Pruning (pre or post) reduces overfitting.

**Similarity:** 0.5564

**Your label:**

**Your notes:**

## R16: function (Tier 3)

**Question:** What is method resolution order (MRO) in Python?

**Answer excerpt:** MRO determines the order Python searches for methods and attributes in class hierarchies with multiple inheritance. Python uses. Some additional details apply.

**Similarity:** 0.3259

**Your label:**

**Your notes:**

## R17: encapsulation (Tier 2)

**Question:** Explain the four pillars of OOP.

**Answer excerpt:** Object oriented design rests on four ideas. First, hiding the internal data of an object behind its public methods. Second, letting a child class reuse the behaviour of its parent. Third, allowing one interface to take many forms by overriding methods on derived types. Fourth, surfacing only the essential operations to clients while keeping implementation details private.

**Similarity:** 0.3983

**Your label:**

**Your notes:**

## R18: inheritance (Tier 2)

**Question:** Explain the four pillars of OOP.

**Answer excerpt:** Object oriented design rests on four ideas. First, hiding the internal data of an object behind its public methods. Second, letting a child class reuse the behaviour of its parent. Third, allowing one interface to take many forms by overriding methods on derived types. Fourth, surfacing only the essential operations to clients while keeping implementation details private.

**Similarity:** 0.5684

**Your label:**

**Your notes:**

## R19: polymorphism (Tier 2)

**Question:** Explain the four pillars of OOP.

**Answer excerpt:** Object oriented design rests on four ideas. First, hiding the internal data of an object behind its public methods. Second, letting a child class reuse the behaviour of its parent. Third, allowing one interface to take many forms by overriding methods on derived types. Fourth, surfacing only the essential operations to clients while keeping implementation details private.

**Similarity:** 0.4095

**Your label:**

**Your notes:**

## R20: abstraction (Tier 2)

**Question:** Explain the four pillars of OOP.

**Answer excerpt:** Object oriented design rests on four ideas. First, hiding the internal data of an object behind its public methods. Second, letting a child class reuse the behaviour of its parent. Third, allowing one interface to take many forms by overriding methods on derived types. Fourth, surfacing only the essential operations to clients while keeping implementation details private.

**Similarity:** 0.4561

**Your label:**

**Your notes:**

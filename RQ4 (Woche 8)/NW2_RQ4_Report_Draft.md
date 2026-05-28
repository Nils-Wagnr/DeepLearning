# From Scratch to Pretrained: When Does Pretraining Pay Off?

## Abstract

This study compares five sentiment-classification approaches on IMDB along a pretraining gradient: an LSTM with random embeddings, an LSTM with frozen GloVe embeddings, a BiLSTM with frozen GloVe embeddings and attention pooling, a fine-tuned DistilBERT model, and prompted LLM classification. The experiment varies the number of labeled training examples (50, 200, 1,000, 5,000, and 25,000) and evaluates all trained models on the full 25,000-example IMDB test set. Results show that pretrained static embeddings and improved aggregation help most when labeled data is scarce, while contextual pretraining becomes increasingly strong once enough fine-tuning data is available. At 200 examples, BiLSTM + GloVe + attention is the strongest trained model in the current run, while DistilBERT becomes strongest from 1,000 examples onward. The full-data BiLSTM result is close to the previous RQ3 TextCNN baseline, suggesting that the earlier LSTM weakness was partly due to representation and pooling rather than recurrence alone.

Note: prompting code is configured for full-test evaluation, but the currently exported prompting rows are marked as stale subset runs until the notebook is rerun on the full IMDB test set.

## 1. Introduction

The amount of labeled data strongly influences which NLP approach is practical. A model trained from scratch must learn both task behavior and useful word representations from the labeled examples, while pretrained embeddings, contextual transformers, or prompted LLMs bring increasing amounts of prior linguistic knowledge.

The research question is: how do a from-scratch LSTM, an LSTM with GloVe embeddings, a BiLSTM with GloVe and attention pooling, a fine-tuned BERT-style model, and a prompted LLM compare on IMDB sentiment classification, and how much does each improvement contribute?

The comparison decomposes the path from an RQ3-style LSTM to BERT into three gaps: representation quality (random embeddings to GloVe), architecture and pooling (unidirectional LSTM to BiLSTM with attention), and contextual pretraining (BiLSTM + GloVe + attention to DistilBERT).

## 2. Methods

The dataset is the IMDB Large Movie Review Dataset loaded via HuggingFace `load_dataset("imdb")`, with 25,000 training reviews and 25,000 test reviews. Training subsets of 50, 200, 1,000, and 5,000 examples are sampled in a balanced way with equal positive and negative examples. The full 25,000-example training set is also used. Each training size is repeated over three random seeds.

Model 1 is an LSTM with random trainable embeddings, embedding dimension 100, hidden dimension 128, one recurrent layer, Adam optimizer with learning rate 1e-3, and 10 epochs. Model 2 keeps the same LSTM architecture but initializes the embedding layer with frozen GloVe 6B 100d vectors. Model 3 uses frozen GloVe embeddings, a bidirectional LSTM, and learned attention pooling over hidden states. Model 4 fine-tunes DistilBERT with HuggingFace `Trainer`, learning rate 2e-5, 3 epochs, and batch size 16. Model 5 uses prompting without weight updates, with zero-shot and few-shot variants.

All trained models are evaluated on the full 25,000-example test set. Metrics are accuracy, macro-F1, wall-clock training time, and inference time per evaluated example. For prompting, the notebook records parse rate, unparsed outputs, accuracy on all examples, and accuracy on parsed examples. The results table stores mean and standard deviation across seeds where applicable.

## 3. Results

The central result is the accuracy-vs-training-size plot exported as `rq4_outputs/rq4_accuracy_vs_size.png`. The corresponding table is exported as `rq4_outputs/rq4_results_table.csv` and `rq4_outputs/rq4_results_table.md`.

Current trained-model findings:

| Finding | Current result |
| --- | ---: |
| Representation gap at N=200 | +0.0038 |
| Architecture/pooling gap at N=200 | +0.1208 |
| Contextual pretraining gap at N=200 | -0.0069 |
| Best trained model at N=200 | BiLSTM + GloVe + Attention |
| Best trained accuracy at N=200 | 0.6288 |
| Size where DistilBERT becomes strongest | 1,000 examples |
| BiLSTM full-data accuracy | 0.8654 |
| Previous RQ3 TextCNN best accuracy | 0.8710 |
| BiLSTM vs. RQ3 TextCNN gap | -0.0056 |

The representation gap is modest at 200 examples in the current run, while architecture and pooling provide a substantially larger improvement. DistilBERT is not the best trained model at 200 examples in this run, but it becomes the strongest approach from 1,000 examples onward.

Prompting rows are currently included in the exported table with `evaluation_status = STALE_SUBSET_RUN_EXPECTED_25000`. These rows should not be interpreted as final assignment results until the prompting cells are rerun on the full 25,000-example test set.

## 4. Discussion

The results indicate that improving the LSTM representation alone is not sufficient to explain the full gap to transformer-based models. Frozen GloVe embeddings add useful semantic information, but the larger gain at small data sizes comes from bidirectionality and attention pooling, which reduce the bottleneck of relying on the final LSTM state.

The full-data BiLSTM + GloVe + attention model nearly matches the previous RQ3 TextCNN result. This supports the interpretation that the RQ3 LSTM underperformance was not simply caused by recurrence being unsuitable for IMDB sentiment. Instead, representation quality and pooling strategy were important limitations.

DistilBERT becomes strongest once enough labeled data is available for fine-tuning. Its remaining advantage over BiLSTM + GloVe + attention represents the contextual pretraining premium: BERT-style models bring pretrained contextual representations that static embeddings cannot provide.

For practical use, a small labeled-data budget favors pretrained representations and strong pooling. With a few hundred labels, BiLSTM + GloVe + attention can be competitive and comparatively cheap to run. From around 1,000 labeled examples in the current experiment, fine-tuned DistilBERT is the recommended choice if training cost is acceptable. Prompting remains useful when no training is possible, but its final comparison requires the full-test prompting rerun.

Limitations include the use of DistilBERT rather than full BERT, the cost of full-test prompting, and reliance on a single dataset. The prompting results also depend on model choice, decoding settings, and prompt wording.

## References

Devlin, J. et al. (2019). BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding.

Brown, T. B. et al. (2020). Language Models are Few-Shot Learners.

Hochreiter, S. and Schmidhuber, J. (1997). Long Short-Term Memory.

Pennington, J., Socher, R., and Manning, C. D. (2014). GloVe: Global Vectors for Word Representation.

Kim, Y. (2014). Convolutional Neural Networks for Sentence Classification.

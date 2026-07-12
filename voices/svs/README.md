# SVS voicebanks (DiffSinger)

Drop **DiffSinger voicebanks in OpenUtau format** here — one folder per bank:

```
voices/svs/
  MyBank/
    dsconfig.yaml
    acoustic.onnx
    phonemes.txt
    dsdict*.yaml
  nsf_hifigan/        ← shared vocoder (Voices page → "Install vocoder")
```

A voicebank is a model **trained to sing**. When one is installed, vocal
tracks are sung by the bank with natural sustained vowels and phrasing, then
converted to your trained AI voice (RVC) — the highest-quality singing the
studio can produce.

Where to get banks: voicebank creators publish them on their own pages
(OpenUtau community, e.g. English banks such as SOLARIA Lite or Peiton).
**Respect each bank's license** — banks are used from this folder only and
are never redistributed by mITyStudio.

Lyrics in a language the bank's dictionary doesn't cover automatically fall
back to the speech-clone engine, so songs never go silent.

import React, { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Download, Volume2, VolumeX } from 'lucide-react';
import { createSpeaker } from '../../lib/speech/tts';

/** A text replay of saved answers; no audio recording is implied. */
export default function TranscriptReview({ rounds }) {
  const turns = rounds.filter(round => round.roundType === 'technical_short_answer' && round.answer?.trim());
  const [index, setIndex] = useState(0);
  const [supported, setSupported] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const speakerRef = useRef(null);

  useEffect(() => {
    const speaker = createSpeaker({ onStart: () => setSpeaking(true), onEnd: () => setSpeaking(false) });
    speakerRef.current = speaker;
    setSupported(speaker.supported);
    return () => { speaker.cancel(); speakerRef.current = null; };
  }, []);

  if (!turns.length) return null;
  const current = turns[Math.min(index, turns.length - 1)];
  function move(next) {
    speakerRef.current?.cancel();
    setIndex(next);
  }
  function download() {
    const text = turns.map(turn => `Round ${turn.id}\nQuestion: ${turn.question}\nAnswer: ${turn.answer}`).join('\n\n');
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'interviv-transcript.txt';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  return <section className="iv-transcript" aria-labelledby="transcript-title">
    <div className="iv-transcript-header"><div><p className="iv-page-kicker">Your conversation</p><h2 id="transcript-title">Transcript &amp; replay</h2>
      <p>Review saved answers from this session. Replay uses your browser's synthesized voice; it is not a recording.</p></div>
      <button type="button" className="app-button" onClick={download}><Download size={16} aria-hidden="true" /> Download text</button>
    </div>
    <div className="iv-transcript-turn"><p className="iv-page-kicker">Question {index + 1} of {turns.length}</p><h3>{current.question}</h3>
      <p className="iv-transcript-label">Your answer</p><p className="iv-transcript-answer">{current.answer}</p>
    </div>
    <div className="iv-transcript-controls">
      <button type="button" className="app-button" disabled={index === 0} onClick={() => move(index - 1)}><ChevronLeft size={16} /> Previous</button>
      <button type="button" className="app-button" disabled={index === turns.length - 1} onClick={() => move(index + 1)}>Next <ChevronRight size={16} /></button>
      {supported && <button type="button" className="app-button" onClick={() => speaking ? speakerRef.current?.cancel() : speakerRef.current?.speak(`Question. ${current.question}. Your answer. ${current.answer}`)}>
        {speaking ? <><VolumeX size={16} /> Stop replay</> : <><Volume2 size={16} /> Read aloud</>}
      </button>}
    </div>
    {supported && <p className="iv-insight-note">Read aloud plays up to the first 1,200 characters. Download text for the full transcript.</p>}
  </section>;
}

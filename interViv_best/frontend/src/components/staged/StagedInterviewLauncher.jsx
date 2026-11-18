import React, { useEffect, useRef, useState } from 'react';
import { createStagedLauncherController, initialLauncherState } from '../../lib/stagedLauncher';
import { markVoiceInterview } from '../../lib/speech/voiceSession';
import StagedLauncherCard from './StagedLauncherCard';

export default function StagedInterviewLauncher({ userId, onStarted }) {
  const [view, setView] = useState(() => initialLauncherState(userId));
  const [voice, setVoice] = useState(false);
  const voiceOn = useRef(false);
  voiceOn.current = voice;
  const controller = useRef(null);
  const started = useRef(onStarted);
  started.current = onStarted;
  useEffect(() => {
    const current = createStagedLauncherController({ userId, onChange: setView,
      onStarted: session => {
        markVoiceInterview(session?.session_id, voiceOn.current);
        started.current?.(session);
      } });
    controller.current = current;
    setView(current.snapshot());
    current.restoreSkills();
    return () => { current.dispose(); controller.current = null; };
  }, [userId]);
  return <StagedLauncherCard {...view} voiceInterview={voice} onVoiceChange={setVoice}
    onSkillsChange={skills => controller.current?.selectSkills(skills)}
    onStart={() => controller.current?.start()} />;
}

import React, { useEffect, useRef, useState } from 'react';
import { createStagedLauncherController, initialLauncherState } from '../../lib/stagedLauncher';
import StagedLauncherCard from './StagedLauncherCard';

export default function StagedInterviewLauncher({ userId, onStarted }) {
  const [view, setView] = useState(() => initialLauncherState(userId));
  const controller = useRef(null);
  const started = useRef(onStarted);
  started.current = onStarted;
  useEffect(() => {
    const current = createStagedLauncherController({ userId, onChange: setView,
      onStarted: session => started.current?.(session) });
    controller.current = current;
    setView(current.snapshot());
    current.restoreSkills();
    return () => { current.dispose(); controller.current = null; };
  }, [userId]);
  return <StagedLauncherCard {...view}
    onSkillsChange={skills => controller.current?.selectSkills(skills)}
    onStart={() => controller.current?.start()} />;
}

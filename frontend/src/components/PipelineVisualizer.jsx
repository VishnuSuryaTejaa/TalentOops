import React from 'react';
import SignalChainRail from './SignalChainRail';

/**
 * PipelineVisualizer wrapper using the new SignalChainRail component.
 * Maps legacy agent node ids to the Signal Chain Rail stages.
 */
export default function PipelineVisualizer({
  activeNode = 'sourcing',
  completedNodes = [],
  onStageSelect,
  runTitle = 'Hire Senior Engineer',
  isLive = false
}) {
  // Normalize legacy node names if needed
  const normalizedActive = (activeNode || 'sourcing').toLowerCase();
  
  return (
    <SignalChainRail
      activeStage={normalizedActive}
      completedStages={completedNodes}
      onStageSelect={onStageSelect}
      runTitle={runTitle}
      isLive={isLive}
    />
  );
}

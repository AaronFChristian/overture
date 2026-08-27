import type { PipelineStage } from "../api";

interface TimelineProps {
  stages: PipelineStage[];
  /** Stage IDs that have started, in arrival order. */
  reached: string[];
  /** True while the pipeline is still running. */
  running: boolean;
  /** Latest detail line for the active stage. */
  activeDetail: string | null;
}

export function PipelineTimeline({ stages, reached, running, activeDetail }: TimelineProps) {
  // The last stage we've heard about is the one currently in flight
  // (a stage emits when it STARTS, not when it finishes -- see
  // decisions.md D-0049), so everything before it is genuinely done.
  const activeIndex = reached.length - 1;

  return (
    <ol className="timeline">
      {stages.map((stage, i) => {
        const isDone = i < activeIndex || (!running && reached.includes(stage.id));
        const isActive = running && i === activeIndex;
        const state = isDone ? "done" : isActive ? "active" : "pending";

        return (
          <li key={stage.id} className={`timeline-step timeline-step--${state}`}>
            <span className="timeline-marker" aria-hidden="true">
              {isDone ? "✓" : isActive ? "●" : "○"}
            </span>
            <div className="timeline-body">
              <span className="timeline-label">{stage.label}</span>
              {isActive && activeDetail && <span className="timeline-detail">{activeDetail}</span>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

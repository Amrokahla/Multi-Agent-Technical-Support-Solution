import type { ReactNode } from "react";

// A numbered pipeline stage. The order is a real dependency (each stage consumes
// the previous), so the numbering encodes meaning rather than decoration.
export default function Stage({
  num,
  kicker,
  title,
  note,
  children,
}: {
  num: string;
  kicker: string;
  title: string;
  note?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="stage">
      <div className="stage-head">
        <span className="stage-num">{num}</span>
        <div>
          <div className="stage-kicker">{kicker}</div>
          <h2 className="stage-title">{title}</h2>
        </div>
        {note && <p className="stage-note">{note}</p>}
      </div>
      {children}
    </section>
  );
}

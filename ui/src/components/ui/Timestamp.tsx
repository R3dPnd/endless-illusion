import { fmtTime } from "../../util";

export default function Timestamp({ ts }: { ts: number }) {
  return <span className="t">{fmtTime(ts)}</span>;
}

/** Program URLs come from agents and pages; open them without referrer or opener. */
export default function ExternalLink({ href }: { href: string }) {
  const safe = /^https?:\/\//i.test(href) ? href : undefined;
  return safe ? (
    <a className="ext-link" href={safe} target="_blank" rel="noopener noreferrer">
      {href}
    </a>
  ) : (
    <span className="ext-link">{href}</span>
  );
}

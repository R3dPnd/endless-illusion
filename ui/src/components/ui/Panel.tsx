import type { ReactNode } from "react";

interface Props {
  title: string;
  as?: "section" | "aside";
  className?: string;
  children: ReactNode;
}

export default function Panel({ title, as: Tag = "section", className = "", children }: Props) {
  return (
    <Tag className={`panel ${className}`}>
      <h2>{title}</h2>
      {children}
    </Tag>
  );
}

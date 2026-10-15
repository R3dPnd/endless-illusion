import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "danger" | "ghost" | "link";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export default function Button({ variant = "ghost", className = "", type = "button", ...rest }: Props) {
  return <button type={type} className={`btn btn--${variant} ${className}`} {...rest} />;
}

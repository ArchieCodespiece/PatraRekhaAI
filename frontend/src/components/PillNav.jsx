import Link from "next/link";

export default function PillNav({ items = [], className = "", itemClassName = "" }) {
    return (
        <nav className={`relative z-[100] flex items-center gap-3 ${className}`} aria-label="Quick navigation">
            {items.map((item) => (
                <Link
                    key={item.label}
                    href={item.href}
                    onClick={item.onClick}
                    className={`group inline-flex items-center gap-3 rounded-full border border-[#CABDB2] bg-[#FFFBF0] px-6 py-3 text-base font-semibold text-[#413632] shadow-md shadow-[#413632]/10 transition-all duration-200 hover:-translate-y-0.5 hover:border-[#CA8A78] hover:bg-[#CA8A78] hover:text-[#FFFBF0] hover:shadow-lg hover:shadow-[#CA8A78]/30 ${itemClassName}`}
                >
                    <span>{item.label}</span>
                    <span className="transition-transform duration-200 group-hover:translate-x-0.5">{item.icon}</span>
                </Link>
            ))}
        </nav>
    );
}

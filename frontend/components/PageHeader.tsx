export function PageHeader({
  title,
  subtitle,
  online,
}: {
  title: string;
  subtitle?: string;
  online?: boolean;
}) {
  return (
    <div className="mb-8 flex items-start justify-between">
      <div>
        <h1 className="font-display text-2xl font-semibold tracking-tight text-text-primary">
          {title}
        </h1>
        {subtitle && <p className="mt-1 font-body text-sm text-text-secondary">{subtitle}</p>}
      </div>
      {online !== undefined && (
        <span
          className={`flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest ${
            online ? "text-success" : "text-error"
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              online ? "bg-success" : "bg-error"
            }`}
          />
          {online ? "harness online" : "harness offline"}
        </span>
      )}
    </div>
  );
}

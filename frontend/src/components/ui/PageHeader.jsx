function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="text-sm text-light">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-1">{actions}</div>}
    </div>
  );
}

export default PageHeader;

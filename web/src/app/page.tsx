import { CoverageGrid } from "@/components/coverage/coverage-grid";
import { providers } from "@/lib/data";

export default function Home() {
  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Employee field coverage</h1>
      <p className="mt-2 max-w-3xl text-neutral-600">
        Every canonical employee field, for PrismHR, isolved and UKG Ready. A count shows how many synthetic
        employees have the field filled. &quot;Not offered&quot; means the provider has no such field for
        reading; &quot;not mapped yet&quot; means the provider has the data but the adapter does not use it.
        Hover a cell for the source path and the spec it rests on.
      </p>
      <div className="mt-8">
        <CoverageGrid providers={providers} />
      </div>
    </div>
  );
}

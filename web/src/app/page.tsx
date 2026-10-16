import { CoverageGrid } from "@/components/coverage/coverage-grid";
import { providers } from "@/lib/data";

export default function Home() {
  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Employee field coverage</h1>
      <p className="mt-2 max-w-3xl text-neutral-600">
        How each provider&apos;s employee fields map into one canonical model. Hover a state or a cell for details.
      </p>
      <div className="mt-8">
        <CoverageGrid providers={providers} />
      </div>
    </div>
  );
}

import { CoverageGrid } from "@/components/coverage/coverage-grid";
import { providers } from "@/lib/data";

export default function Home() {
  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Employee field coverage</h1>
      <div className="mt-6">
        <CoverageGrid providers={providers} />
      </div>
    </div>
  );
}

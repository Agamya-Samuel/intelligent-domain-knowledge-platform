import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * Models page — 4-tier model catalog with fine-tuning triggers.
 * Full catalog API implemented in Week 4.
 */

const MODEL_TIERS = [
  {
    tier: "Tier 0 — Compact",
    description: "Fastest training/inference; good baseline for RAG",
    models: [
      { name: "Qwen 2.5 7B-Instruct", size: "7B", gpu: "A10G", cost: "$1–$3/run" },
      { name: "Gemma 4 E4B", size: "4B", gpu: "A10G", cost: "$1–$2/run" },
    ],
  },
  {
    tier: "Tier 1 — Standard (Recommended)",
    description: "Best quality/cost ratio; strong reasoning across all domains",
    models: [
      { name: "Qwen 2.5 14B-Instruct", size: "14B", gpu: "A10G", cost: "$2–$5/run" },
      { name: "Mistral Ministral 3 14B", size: "14B", gpu: "A10G", cost: "$2–$5/run" },
      { name: "DeepSeek-R1 Distill 14B", size: "14B", gpu: "A10G", cost: "$2–$5/run" },
    ],
  },
  {
    tier: "Tier 2 — Enhanced",
    description: "Near-70B quality at half the VRAM; requires L40S",
    models: [
      { name: "Qwen 2.5 32B-Instruct", size: "32B", gpu: "L40S", cost: "$8–$16/run" },
      { name: "Gemma 4 31B", size: "31B", gpu: "L40S", cost: "$8–$16/run" },
    ],
  },
  {
    tier: "Tier 3 — Maximum",
    description: "Maximum quality; limited runs per month on $30 budget",
    models: [
      { name: "Qwen 2.5 72B-Instruct", size: "72B", gpu: "A100-80GB", cost: "$20–$35/run" },
      { name: "Llama 3.3 70B-Instruct", size: "70B", gpu: "A100-80GB", cost: "$20–$35/run" },
    ],
  },
] as const;

export default function ModelsPage() {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Model Catalog</h1>
        <p className="text-sm text-muted-foreground">
          Browse available models across 4 tiers. Select a model to trigger
          fine-tuning within your $30/month budget.
        </p>
      </div>

      <div className="space-y-8">
        {MODEL_TIERS.map(({ tier, description, models }) => (
          <section key={tier}>
            <div className="mb-3">
              <h2 className="text-base font-semibold">{tier}</h2>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {models.map((model) => (
                <Card key={model.name}>
                  <CardHeader>
                    <CardTitle className="text-sm font-medium">
                      {model.name}
                    </CardTitle>
                    <CardDescription>{model.size} parameters</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-1 text-xs text-muted-foreground">
                    <p>GPU: {model.gpu}</p>
                    <p>Est. cost: {model.cost}</p>
                  </CardContent>
                  <CardFooter>
                    <Button size="sm" variant="outline" disabled>
                      Select &amp; Fine-tune
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

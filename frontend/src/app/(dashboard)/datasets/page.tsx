import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Datasets page — list user datasets, create new, manage sources.
 * Full CRUD implemented in Week 3.
 */
export default function DatasetsPage() {
  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Datasets</h1>
          <p className="text-sm text-muted-foreground">
            Manage versioned datasets for fine-tuning.
          </p>
        </div>
        <Button disabled>Create Dataset</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">No datasets yet</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Create your first dataset to begin fine-tuning. Each dataset can
            contain documents from multiple domains and supports file uploads,
            S3 references, pasted text, and URL fetching.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

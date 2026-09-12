import Documents from "../../../components/documents";

export const metadata = {
    title: "Documents – PatraRekhaAI",
    description: "Processed document summaries, deadlines, and PDF previews.",
};

export default function DocumentPage() {
    return (
        <div className="h-screen bg-background">
            <Documents />
        </div>
    );
}

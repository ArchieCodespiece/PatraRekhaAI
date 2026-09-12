import ChatWithPDF from "../../../components/chatpdf";

export const metadata = {
    title: "Chat with PDF – PatraRekhaAI",
    description: "AI-powered document Q&A. Select PDFs and ask questions.",
};

export default function ChatPage() {
    return (
        <div className="h-screen bg-background">
            <ChatWithPDF />
        </div>
    );
}

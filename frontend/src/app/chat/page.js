import ChatWithPDF from "../../components/chatpdf";

export const metadata = {
    title: "Chat with PDF – PatraRekhaAI",
    description: "AI-powered document Q&A. Select PDFs and ask questions.",
};

export default function ChatPage() {
    return (
        <div className="h-screen p-6 bg-background">
            <ChatWithPDF />
        </div>
    );
}

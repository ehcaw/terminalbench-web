import React from "react";
import dynamic from "next/dynamic";

// Disable SSR for the terminal component since it uses browser APIs
const TerminalIframe = dynamic(() => import("./terminal-iframe"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full bg-black text-white p-4">
      <div className="animate-pulse">Loading terminal...</div>
    </div>
  ),
});

interface TerminalComponentProps {
  userId: string;
  apiBaseUrl?: string;
}

const TerminalComponent: React.FC<TerminalComponentProps> = ({
  userId,
  apiBaseUrl = process.env.NEXT_PUBLIC_REACT_APP_API_URL || "",
}) => {
  return <TerminalIframe userId={userId} apiBaseUrl={apiBaseUrl} />;
};

export default TerminalComponent;

import { NextRequest, NextResponse } from "next/server";
import admin from "firebase-admin";

// Initialize Firebase Admin SDK if not already initialized
if (!admin.apps.length) {
  admin.initializeApp({
    credential: admin.credential.cert({
      projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
      clientEmail: process.env.NEXT_PUBLIC_FIREBASE_CLIENT_EMAIL,
      privateKey: process.env.FIREBASE_PRIVATE_KEY?.replace(/\\n/g, "\n"),
    }),
    storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  });
}

export async function GET(request: NextRequest) {
  try {
    console.log("=== Firebase Storage Debug Info ===");
    console.log(
      "Storage bucket:",
      process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
    );

    // Get Firebase Admin Storage instance
    const bucket = admin.storage().bucket();
    console.log("Bucket name:", bucket.name);

    // Test basic storage connection - list root contents
    console.log("Attempting to list root storage contents...");
    const [rootFiles] = await bucket.getFiles({ maxResults: 10 });
    console.log(
      "Root files:",
      rootFiles.map((file) => file.name),
    );

    // Try to list tasks folder if it exists
    console.log("Attempting to list tasks folder...");
    const [taskFiles] = await bucket.getFiles({
      prefix: "tasks/",
      maxResults: 20,
    });
    console.log(
      "Tasks folder contents:",
      taskFiles.map((file) => file.name),
    );

    // Group files by user
    const userFolders = {};
    taskFiles.forEach((file) => {
      const pathParts = file.name.split("/");
      if (pathParts.length >= 2 && pathParts[0] === "tasks") {
        const userId = pathParts[1];
        if (!userFolders[userId]) {
          userFolders[userId] = [];
        }
        if (pathParts.length > 2) {
          // Only include actual files, not folder markers
          userFolders[userId].push(pathParts.slice(2).join("/"));
        }
      }
    });

    return NextResponse.json({
      success: true,
      bucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
      bucketName: bucket.name,
      config: {
        hasProjectId: !!process.env.FIREBASE_PROJECT_ID,
        hasClientEmail: !!process.env.FIREBASE_CLIENT_EMAIL,
        hasPrivateKey: !!process.env.FIREBASE_PRIVATE_KEY,
      },
      rootFiles: rootFiles.slice(0, 10).map((file) => ({
        name: file.name,
        size: file.metadata?.size,
        contentType: file.metadata?.contentType,
      })),
      tasksStructure: userFolders,
      totalTaskFiles: taskFiles.length,
    });
  } catch (error) {
    console.error("Debug error:", error);
    return NextResponse.json(
      {
        error: "Debug failed",
        message: error.message,
        code: error.code,
        bucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
        config: {
          hasProjectId: !!process.env.FIREBASE_PROJECT_ID,
          hasClientEmail: !!process.env.FIREBASE_CLIENT_EMAIL,
          hasPrivateKey: !!process.env.FIREBASE_PRIVATE_KEY,
        },
        stack: error.stack,
      },
      { status: 500 },
    );
  }
}

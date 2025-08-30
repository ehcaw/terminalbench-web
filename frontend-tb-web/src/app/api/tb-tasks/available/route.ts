import { NextRequest, NextResponse } from "next/server";
import admin from "firebase-admin";

// Initialize Firebase Admin SDK if not already initialized
if (!admin.apps.length) {
  admin.initializeApp({
    credential: admin.credential.cert({
      projectId: process.env.FIREBASE_ADMIN_PROJECT_ID,
      clientEmail: process.env.FIREBASE_ADMIN_CLIENT_EMAIL,
      privateKey: process.env.FIREBASE_ADMIN_PRIVATE_KEY?.replace(/\\n/g, "\n"),
    }),
    storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  });
}

export async function GET(request: NextRequest) {
  try {
    // Get userId from query parameters
    const queryParams = request.nextUrl.searchParams;
    const userId = queryParams.get("userId");
    console.log(userId);

    if (!userId) {
      return NextResponse.json(
        { error: "userId is required" },
        { status: 400 },
      );
    }

    console.log("Attempting to access storage for userId:", userId);
    console.log(
      "Storage bucket:",
      process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
    );

    // Get Firebase Admin Storage instance
    const bucket = admin.storage().bucket();

    // Reference to the tasks folder for the specific user
    const tasksPath = `tasks/${userId}/`;
    console.log("Trying to access path:", tasksPath);

    // List all files in the tasks folder
    const [files] = await bucket.getFiles({
      prefix: tasksPath,
    });

    console.log(
      "Found files:",
      files.map((f) => f.name),
    );

    const tasks: Array<object> = [];

    // Process each file in the folder
    for (const file of files) {
      try {
        // Skip if it's just the folder itself
        if (file.name === tasksPath) continue;

        // Get file metadata
        const [metadata] = await file.getMetadata();

        // Extract task name from the file name (remove path and extension)
        const fileName = file.name.replace(tasksPath, "");
        const taskName = fileName.replace(/\.[^/.]+$/, "");

        // Skip empty filenames
        if (!fileName) continue;

        tasks.push({
          id: fileName, // Use filename as ID
          name: taskName,
          fileName: fileName,
          fullPath: file.name,
          size: metadata.size,
          contentType: metadata.contentType,
          timeCreated: metadata.timeCreated,
          updated: metadata.updated,
          // Default values
          category: "General",
          difficulty: "Unknown",
          description: `Task: ${taskName}`,
        });
      } catch (metadataError) {
        console.warn(`Failed to get metadata for ${file.name}:`, metadataError);
        // Still add the task even if metadata fails
        const fileName = file.name.replace(tasksPath, "");
        const taskName = fileName.replace(/\.[^/.]+$/, "");

        if (fileName) {
          tasks.push({
            id: fileName,
            name: taskName,
            fileName: fileName,
            fullPath: file.name,
            category: "General",
            difficulty: "Unknown",
            description: `Task: ${taskName}`,
          });
        }
      }
    }

    // Sort tasks by name alphabetically
    tasks.sort((a, b) => a.name.localeCompare(b.name));

    console.log("Processed tasks:", tasks.length);

    return NextResponse.json(tasks, { status: 200 });
  } catch (error) {
    console.error("Error fetching available tasks from Storage:", error);
    console.error("Error details:", {
      code: error.code,
      message: error.message,
    });

    // Handle specific errors
    if (error.code === 404) {
      return NextResponse.json(
        {
          error: "Tasks folder not found for this user",
          details: `The path tasks/{userId}} does not exist in your Firebase Storage bucket`,
        },
        { status: 404 },
      );
    } else if (error.code === 403) {
      return NextResponse.json(
        { error: "Unauthorized access to storage" },
        { status: 403 },
      );
    }

    return NextResponse.json(
      {
        error: "Failed to fetch available tasks",
        details: error.message,
        code: error.code,
      },
      { status: 500 },
    );
  }
}

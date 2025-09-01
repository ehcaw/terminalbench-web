import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/firebase';
import { doc, getDoc, updateDoc, addDoc, collection, serverTimestamp } from 'firebase/firestore';

export async function POST(request: NextRequest) {
  try {
    const { taskId } = await request.json();

    if (!taskId) {
      return NextResponse.json(
        { error: 'Task ID is required' },
        { status: 400 }
      );
    }

    // Get the task document
    const taskRef = doc(db, 'tasks', taskId);
    const taskDoc = await getDoc(taskRef);

    if (!taskDoc.exists()) {
      return NextResponse.json(
        { error: 'Task not found' },
        { status: 404 }
      );
    }

    const taskData = taskDoc.data();

    // Check if task is available
    if (taskData.status !== 'available') {
      return NextResponse.json(
        { error: 'Task is not available' },
        { status: 400 }
      );
    }

    // Update the task status to 'running'
    await updateDoc(taskRef, {
      status: 'running',
      startedAt: serverTimestamp(),
      updatedAt: serverTimestamp(),
    });

    // Create a running task entry
    const runningTaskRef = await addDoc(collection(db, 'runningTasks'), {
      taskId: taskId,
      name: taskData.name,
      description: taskData.description,
      status: 'In Progress',
      startedAt: serverTimestamp(),
      createdAt: serverTimestamp(),
    });

    return NextResponse.json(
      {
        message: 'Task started successfully',
        runningTaskId: runningTaskRef.id,
        taskId: taskId
      },
      { status: 200 }
    );
  } catch (error) {
    console.error('Error starting task:', error);
    return NextResponse.json(
      { error: 'Failed to start task' },
      { status: 500 }
    );
  }
}

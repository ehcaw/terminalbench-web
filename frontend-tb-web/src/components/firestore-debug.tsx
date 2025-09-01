"use client";

import { useState } from "react";
import { collection, getDocs, doc, getDoc } from "firebase/firestore";
import { db } from "@/lib/firebase";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "./ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";

export function FirestoreDebug() {
  const { user } = useAuth();
  const [results, setResults] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const addResult = (message: string) => {
    setResults((prev) => [
      ...prev,
      `${new Date().toLocaleTimeString()}: ${message}`,
    ]);
  };

  const testFirestore = async () => {
    if (!user?.uid) {
      addResult("❌ No authenticated user");
      return;
    }

    setLoading(true);
    setResults([]);

    try {
      addResult(`✅ User authenticated: ${user.uid}`);

      // Test 1: Basic Firestore connection
      try {
        const testRef = collection(db, "test");
        addResult("✅ Firestore connection established");
      } catch (err) {
        addResult(`❌ Firestore connection failed: ${err}`);
        return;
      }

      // Test 2: Try to read user_runs collection
      try {
        const userRunsRef = collection(db, "user_runs");
        const snapshot = await getDocs(userRunsRef);
        addResult(
          `✅ user_runs collection accessible, ${snapshot.size} documents found`
        );

        if (snapshot.size > 0) {
          snapshot.forEach((doc, index) => {
            if (index < 3) {
              // Show first 3 docs
              const data = doc.data();
              addResult(
                `📄 Doc ${doc.id}: user_id=${data.user_id}, keys=[${Object.keys(
                  data
                ).join(", ")}]`
              );
            }
          });
        }
      } catch (err) {
        addResult(`❌ user_runs collection failed: ${err}`);
      }

      // Test 3: Try subcollection approach
      try {
        const storeDoc = doc(db, "terminal-bench-web-db-store", "default");
        const subCollection = collection(storeDoc, "user_runs");
        const subSnapshot = await getDocs(subCollection);
        addResult(
          `✅ Subcollection accessible, ${subSnapshot.size} documents found`
        );
      } catch (err) {
        addResult(`❌ Subcollection failed: ${err}`);
      }

      // Test 4: Try different collection names
      const collectionNames = [
        "runs",
        "task_runs",
        "user_tasks",
        "terminal_bench_runs",
        "terminal-bench-web-db-store",
      ];

      for (const name of collectionNames) {
        try {
          const testCollection = collection(db, name);
          const testSnapshot = await getDocs(testCollection);
          if (testSnapshot.size > 0) {
            addResult(
              `✅ Found collection '${name}' with ${testSnapshot.size} documents`
            );
          }
        } catch (err) {
          // Silently continue
        }
      }
    } catch (err) {
      addResult(`❌ General error: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Firestore Debug Tool</CardTitle>
        <CardDescription>
          Test Firestore connectivity and collection access
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button onClick={testFirestore} disabled={loading}>
          {loading ? "Testing..." : "Run Firestore Tests"}
        </Button>

        {results.length > 0 && (
          <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-lg max-h-96 overflow-y-auto">
            <h4 className="font-semibold mb-2">Test Results:</h4>
            {results.map((result, index) => (
              <div key={index} className="text-sm font-mono mb-1">
                {result}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

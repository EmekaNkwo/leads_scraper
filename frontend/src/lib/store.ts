import { configureStore } from "@reduxjs/toolkit";
import { scraperApi } from "./scraper-api";

export const store = configureStore({
  reducer: {
    [scraperApi.reducerPath]: scraperApi.reducer,
  },
  middleware: (getDefault) => getDefault().concat(scraperApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

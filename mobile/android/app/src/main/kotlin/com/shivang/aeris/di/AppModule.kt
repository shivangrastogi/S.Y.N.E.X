package com.shivang.aeris.di

import android.content.Context
import androidx.room.Room
import com.shivang.aeris.core.brain.Skill
import com.shivang.aeris.data.db.AerisDatabase
import com.shivang.aeris.data.db.dao.ExpenseDao
import com.shivang.aeris.data.db.dao.MeetingDao
import com.shivang.aeris.data.db.dao.MessageDao
import com.shivang.aeris.data.db.dao.ReminderDao
import com.shivang.aeris.data.db.dao.SearchCacheDao
import com.shivang.aeris.data.db.dao.TaskDao
import com.shivang.aeris.skills.ExpenseSkill
import com.shivang.aeris.skills.MonthSummarySkill
import com.shivang.aeris.skills.OcrSkill
import com.shivang.aeris.skills.ReminderSkill
import com.shivang.aeris.skills.SystemHealthSkill
import com.shivang.aeris.skills.TaskSkill
import com.shivang.aeris.skills.TimerSkill
import com.shivang.aeris.skills.VisionSkill
import com.shivang.aeris.skills.WebSearchSkill
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import dagger.multibindings.IntoSet
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides @Singleton
    fun provideDb(@ApplicationContext ctx: Context): AerisDatabase =
        Room.databaseBuilder(ctx, AerisDatabase::class.java, "aeris.db")
            .fallbackToDestructiveMigration()
            .build()

    @Provides fun expense(db: AerisDatabase): ExpenseDao = db.expenseDao()
    @Provides fun task(db: AerisDatabase): TaskDao = db.taskDao()
    @Provides fun reminder(db: AerisDatabase): ReminderDao = db.reminderDao()
    @Provides fun meeting(db: AerisDatabase): MeetingDao = db.meetingDao()
    @Provides fun message(db: AerisDatabase): MessageDao = db.messageDao()
    @Provides fun cache(db: AerisDatabase): SearchCacheDao = db.searchCacheDao()
}

@Module
@InstallIn(SingletonComponent::class)
abstract class SkillModule {
    @Binds @IntoSet abstract fun bindExpense(s: ExpenseSkill): Skill
    @Binds @IntoSet abstract fun bindMonthSummary(s: MonthSummarySkill): Skill
    @Binds @IntoSet abstract fun bindTask(s: TaskSkill): Skill
    @Binds @IntoSet abstract fun bindReminder(s: ReminderSkill): Skill
    @Binds @IntoSet abstract fun bindTimer(s: TimerSkill): Skill
    @Binds @IntoSet abstract fun bindWebSearch(s: WebSearchSkill): Skill
    @Binds @IntoSet abstract fun bindVision(s: VisionSkill): Skill
    @Binds @IntoSet abstract fun bindOcr(s: OcrSkill): Skill
    @Binds @IntoSet abstract fun bindHealth(s: SystemHealthSkill): Skill
}
